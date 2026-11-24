"""The crashtest agent.

``CheatAgent`` is a Harbor custom agent (subclass of Harbor's ``BaseAgent``) that,
instead of calling an LLM, uploads a chosen cheat into the task environment and
runs it. ``harbor run`` then grades the result with the task's own ``test.sh``.

Harbor is an *optional* dependency. When it is not importable (CI, the self-test
suite, anyone reading the code) we fall back to a tiny abstract base so the module
imports cleanly. The real cheat-application logic lives in :func:`apply_cheat`,
which takes plain callables and so is unit-testable with no harness at all.

WEEK-1 / unverified (tracked in docs/open-questions.md):
  * The exact import path of Harbor's ``BaseAgent`` and the shape of its env
    object (``exec``/``upload`` method names, the Trial/Context types). The
    import is attempted across the paths the docs suggest; adjust once pinned.
  * Whether ``setsid`` children survive until the verifier runs (cheat C02).
  * Whether an uploaded ``/tests`` merges into or replaces the existing one (C03).
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .cheatspec import Cheat, load_cheat
from .registry import find_cheat

# Where the cheat's scripts are uploaded inside the task environment.
REMOTE_CHEAT_DIR = "/tmp/.crashtest"
# The honesty marker: every cheat run writes what it touched here.
MANIFEST_PATH = "/logs/agent/crashtest.json"

# --- Harbor BaseAgent import, with a local fallback -------------------------

_HARBOR_BASE = None
for _path in ("harbor.agents", "harbor.agent", "harbor"):
    try:  # pragma: no cover - depends on whether harbor is installed
        _mod = __import__(_path, fromlist=["BaseAgent"])
        _HARBOR_BASE = getattr(_mod, "BaseAgent")
        break
    except Exception:
        continue

if _HARBOR_BASE is None:  # pragma: no cover - the common case off-harness

    class _BaseAgent:
        """Minimal stand-in for Harbor's BaseAgent so the module imports.

        Only the surface crashtest uses is declared. Replace behaviour by
        subclassing; the real Harbor base is used automatically when installed.
        """

        def name(self) -> str:  # noqa: D401
            raise NotImplementedError

        def version(self) -> str:
            raise NotImplementedError

        def setup(self, env: Any) -> None:
            return None

        def run(self, instruction: str, env: Any, context: Any = None) -> Any:
            raise NotImplementedError

    BaseAgentBase = _BaseAgent
else:  # pragma: no cover
    BaseAgentBase = _HARBOR_BASE


# --- The testable core ------------------------------------------------------


@dataclass
class CheatOutcome:
    """What a cheat run did, independent of the grader's later reward."""

    cheat_id: str
    cheat_version: str
    applied: bool
    probe_exit: int
    payload_exit: Optional[int]
    touched: list[str]
    error: Optional[str] = None

    def manifest(self) -> dict:
        return {
            "tool": "crashtest",
            "cheat_id": self.cheat_id,
            "cheat_version": self.cheat_version,
            "applied": self.applied,
            "probe_exit": self.probe_exit,
            "payload_exit": self.payload_exit,
            "touched": self.touched,
            "error": self.error,
        }


# An exec callable runs a shell command in the environment and returns
# (exit_code, stdout, stderr). An upload callable copies a local dir to a remote
# path. Both are supplied by the Harbor adapter (or by tests).
ExecFn = Callable[[str], "tuple[int, str, str]"]
UploadFn = Callable[[Path, str], None]
WriteFn = Callable[[str, str], None]


def apply_cheat(
    cheat: Cheat,
    *,
    exec_fn: ExecFn,
    upload_fn: UploadFn,
    write_fn: WriteFn,
) -> CheatOutcome:
    """Upload a cheat into an environment, probe, and run its payload.

    * ``upload_fn`` copies the cheat directory to ``REMOTE_CHEAT_DIR``.
    * ``exec_fn`` runs ``probe.sh`` then (if it applies) ``payload.sh``.
    * ``write_fn`` writes the honesty manifest to ``MANIFEST_PATH``.

    The cheat's own scripts decide what "touched" means; we read the trailing
    ``CRASHTEST_TOUCHED=`` lines the payload may print. ``/solution`` is never
    touched here, by construction: crashtest only ever uploads to
    ``REMOTE_CHEAT_DIR`` and runs the cheat's two scripts.
    """
    meta = cheat.meta
    upload_fn(cheat.directory, REMOTE_CHEAT_DIR)

    probe_cmd = f"sh {shlex.quote(REMOTE_CHEAT_DIR + '/probe.sh')}"
    probe_exit, _p_out, _p_err = exec_fn(probe_cmd)

    if probe_exit == meta.na_exit_code:
        outcome = CheatOutcome(
            cheat_id=meta.id,
            cheat_version=meta.version,
            applied=False,
            probe_exit=probe_exit,
            payload_exit=None,
            touched=[],
        )
        _safe_write_manifest(write_fn, outcome)
        return outcome

    payload_cmd = f"sh {shlex.quote(REMOTE_CHEAT_DIR + '/payload.sh')}"
    payload_exit, out, _err = exec_fn(payload_cmd)
    touched = _parse_touched(out)

    outcome = CheatOutcome(
        cheat_id=meta.id,
        cheat_version=meta.version,
        applied=True,
        probe_exit=probe_exit,
        payload_exit=payload_exit,
        touched=touched,
    )
    _safe_write_manifest(write_fn, outcome)
    return outcome


def _parse_touched(stdout: str) -> list[str]:
    touched: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("CRASHTEST_TOUCHED="):
            touched.append(line[len("CRASHTEST_TOUCHED=") :])
    return touched


def _safe_write_manifest(write_fn: WriteFn, outcome: CheatOutcome) -> None:
    try:
        write_fn(MANIFEST_PATH, json.dumps(outcome.manifest(), indent=2))
    except Exception:  # pragma: no cover - never let the marker break a run
        pass


# --- The Harbor agent -------------------------------------------------------


class CheatAgent(BaseAgentBase):  # type: ignore[misc,valid-type]
    """Harbor custom agent that runs one crashtest cheat instead of an LLM.

    Load it with ``-a crashtest.agent:CheatAgent`` and choose the cheat with
    ``--ak cheat=c02_reward_daemon``.
    """

    def __init__(self, cheat: str | None = None, **kwargs: Any) -> None:
        # Harbor passes --ak key=value pairs as constructor kwargs.
        super().__init__(**kwargs) if _HARBOR_BASE is not None else None
        import os

        cheat_id = cheat or os.environ.get("CRASHTEST_CHEAT")
        if not cheat_id:
            raise ValueError(
                "No cheat selected. Pass --ak cheat=<id> (e.g. cheat=c02_reward_daemon)."
            )
        self._cheat: Cheat = find_cheat(cheat_id)

    def name(self) -> str:
        return "crashtest"

    def version(self) -> str:
        return f"crashtest/{self._cheat.meta.id}@{self._cheat.meta.version}"

    def setup(self, env: Any) -> None:
        return None

    def run(self, instruction: str, env: Any, context: Any = None) -> Any:
        """Apply the selected cheat to the task environment.

        Wires Harbor's env methods into :func:`apply_cheat`. The adapter below
        is deliberately forgiving about method names because the exact env API
        is a week-1 verification item.
        """
        exec_fn, upload_fn, write_fn = _adapt_env(env)
        outcome = apply_cheat(
            self._cheat, exec_fn=exec_fn, upload_fn=upload_fn, write_fn=write_fn
        )
        # Harbor does not read our return value for grading (test.sh does), but a
        # structured return helps `harbor analyze` and our own debugging.
        return outcome.manifest()


def _adapt_env(env: Any) -> "tuple[ExecFn, UploadFn, WriteFn]":
    """Build exec/upload/write callables from a Harbor env object.

    Tries the method names Harbor's docs/examples use, with fallbacks. Pin the
    real names in week 1 and delete the guessing.
    """

    def exec_fn(cmd: str) -> tuple[int, str, str]:
        for attr in ("exec", "run", "execute", "shell"):
            fn = getattr(env, attr, None)
            if callable(fn):
                res = fn(cmd)
                return _normalize_exec_result(res)
        raise AttributeError("env has no exec/run/execute/shell method; pin in week 1")

    def upload_fn(local_dir: Path, remote_dir: str) -> None:
        for attr in ("upload_dir", "upload", "put_dir", "copy_in"):
            fn = getattr(env, attr, None)
            if callable(fn):
                fn(str(local_dir), remote_dir)
                return
        # Last resort: shell out a tar stream if only exec is available.
        raise AttributeError("env has no upload_dir/upload/put_dir; pin in week 1")

    def write_fn(remote_path: str, content: str) -> None:
        for attr in ("write_file", "put_file", "write"):
            fn = getattr(env, attr, None)
            if callable(fn):
                fn(remote_path, content)
                return
        # Fall back to writing via exec + a here-doc-free printf.
        ec, _, _ = exec_fn(
            f"mkdir -p {shlex.quote(str(Path(remote_path).parent))} && "
            f"printf %s {shlex.quote(content)} > {shlex.quote(remote_path)}"
        )
        if ec != 0:  # pragma: no cover
            raise OSError(f"could not write manifest to {remote_path}")

    return exec_fn, upload_fn, write_fn


def _normalize_exec_result(res: Any) -> tuple[int, str, str]:
    """Coerce whatever env.exec returns into (exit_code, stdout, stderr)."""
    if isinstance(res, tuple):
        exit_code = int(res[0]) if len(res) > 0 and res[0] is not None else 0
        out = res[1] if len(res) > 1 and res[1] is not None else ""
        err = res[2] if len(res) > 2 and res[2] is not None else ""
        return exit_code, str(out), str(err)
    # Object-style result, e.g. CompletedProcess-like.
    exit_code = int(
        getattr(res, "exit_code", getattr(res, "returncode", getattr(res, "code", 0))) or 0
    )
    out = str(getattr(res, "stdout", getattr(res, "output", "")) or "")
    err = str(getattr(res, "stderr", "") or "")
    return exit_code, out, err


__all__ = [
    "CheatAgent",
    "CheatOutcome",
    "apply_cheat",
    "REMOTE_CHEAT_DIR",
    "MANIFEST_PATH",
]
