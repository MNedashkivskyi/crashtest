"""The crashtest agent.

``CheatAgent`` is a Harbor custom agent (subclass of Harbor's ``BaseAgent``) that,
instead of calling an LLM, uploads a chosen cheat into the task environment and
runs it. ``harbor run`` then grades the result with the task's own verifier.

This is written against Harbor 0.27.0's real ``BaseAgent`` API (confirmed by
reading ``harbor/agents/base.py`` and ``oracle.py``):

  * ``name()`` is a ``@staticmethod`` returning the agent name.
  * ``version(self)`` is an instance method.
  * ``setup(self, environment)`` and ``run(self, instruction, environment,
    context)`` are ``async``. ``run`` returns ``None`` — the reward comes from the
    task's verifier, not from the agent.
  * The environment exposes ``await environment.upload_dir(source_dir=,
    target_dir=)`` and ``await environment.exec(command=, user=)`` returning a
    result with ``.return_code`` (mirrors the oracle agent running solve.sh).
  * ``--ak cheat=<id>`` arrives as the ``cheat`` constructor kwarg; the base
    ``__init__`` takes ``logs_dir`` first.

Harbor is an optional dependency: when it is not importable (CI, the self-test
suite) we fall back to a tiny base so the module imports. The cheat-application
logic lives in :func:`apply_cheat`, which takes plain async callables and so is
unit-testable with no harness.
"""

from __future__ import annotations

import json
import os
import shlex
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .cheatspec import Cheat
from .registry import find_cheat

# Where the cheat's scripts are uploaded inside the task environment.
REMOTE_CHEAT_DIR = "/tmp/.crashtest"
# The honesty marker filename, written under the environment's agent log dir.
MARKER_FILENAME = "crashtest.json"

# --- Harbor BaseAgent import, with a local fallback -------------------------

_HARBOR_BASE = None
for _path in ("harbor.agents.base", "harbor.agents", "harbor.agent"):
    try:  # pragma: no cover - depends on whether harbor is installed
        _mod = __import__(_path, fromlist=["BaseAgent"])
        _HARBOR_BASE = _mod.BaseAgent
        break
    except Exception:
        continue

if _HARBOR_BASE is None:  # pragma: no cover - the common case off-harness

    class _BaseAgentShim:
        """Minimal stand-in so the module imports without Harbor installed.

        Only present to let ``CheatAgent`` be defined; the real Harbor base is
        used automatically when installed. Not a functional agent off-harness.
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    BaseAgentBase: Any = _BaseAgentShim
else:  # pragma: no cover
    BaseAgentBase = _HARBOR_BASE


# --- the testable core ------------------------------------------------------


@dataclass
class CheatOutcome:
    """What a cheat run did, independent of the grader's later reward."""

    cheat_id: str
    cheat_version: str
    applied: bool
    probe_exit: int
    payload_exit: int | None
    touched: list[str]
    error: str | None = None

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
# (return_code, stdout). An upload callable copies a local dir to a remote path.
# Both are async, matching Harbor's environment API; tests supply fakes.
ExecFn = Callable[[str], Awaitable["tuple[int, str]"]]
UploadFn = Callable[[str, str], Awaitable[None]]


async def apply_cheat(
    cheat: Cheat,
    *,
    exec_fn: ExecFn,
    upload_fn: UploadFn,
    agent_dir: str,
) -> CheatOutcome:
    """Upload a cheat into an environment, probe, and run its payload.

    ``/solution`` is never touched here by construction: crashtest only uploads
    to ``REMOTE_CHEAT_DIR`` and runs the cheat's own two scripts. The honesty
    marker is written under ``agent_dir`` (the environment's agent log dir).
    """
    meta = cheat.meta
    await upload_fn(str(cheat.directory), REMOTE_CHEAT_DIR)

    probe_cmd = f"sh {shlex.quote(REMOTE_CHEAT_DIR + '/probe.sh')}"
    probe_exit, _out = await exec_fn(probe_cmd)

    if probe_exit == meta.na_exit_code:
        outcome = CheatOutcome(
            cheat_id=meta.id,
            cheat_version=meta.version,
            applied=False,
            probe_exit=probe_exit,
            payload_exit=None,
            touched=[],
        )
        await _write_marker(exec_fn, agent_dir, outcome)
        return outcome

    payload_cmd = f"sh {shlex.quote(REMOTE_CHEAT_DIR + '/payload.sh')}"
    payload_exit, out = await exec_fn(payload_cmd)
    outcome = CheatOutcome(
        cheat_id=meta.id,
        cheat_version=meta.version,
        applied=True,
        probe_exit=probe_exit,
        payload_exit=payload_exit,
        touched=_parse_touched(out),
    )
    await _write_marker(exec_fn, agent_dir, outcome)
    return outcome


def _parse_touched(stdout: str) -> list[str]:
    touched: list[str] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("CRASHTEST_TOUCHED="):
            touched.append(line[len("CRASHTEST_TOUCHED=") :])
    return touched


async def _write_marker(exec_fn: ExecFn, agent_dir: str, outcome: CheatOutcome) -> None:
    # JSON uses only double quotes, so single-quoting the whole payload is safe.
    try:
        agent_dir = agent_dir.rstrip("/") or "/logs/agent"
        path = f"{agent_dir}/{MARKER_FILENAME}"
        content = json.dumps(outcome.manifest())
        cmd = (
            f"mkdir -p {shlex.quote(agent_dir)} && "
            f"printf %s {shlex.quote(content)} > {shlex.quote(path)}"
        )
        await exec_fn(cmd)
    except Exception:  # pragma: no cover - never let the marker break a run
        pass


# --- the Harbor agent -------------------------------------------------------


class CheatAgent(BaseAgentBase):  # type: ignore[misc,valid-type]
    """Harbor custom agent that runs one crashtest cheat instead of an LLM.

    Load it with ``-a crashtest.agent:CheatAgent`` and choose the cheat with
    ``--ak cheat=c02_reward_daemon``.
    """

    def __init__(self, logs_dir: Any = None, *, cheat: str | None = None, **kwargs: Any) -> None:
        if _HARBOR_BASE is not None:  # pragma: no cover - only under real harbor
            super().__init__(logs_dir=logs_dir, **kwargs)
        cheat_id = cheat or os.environ.get("CRASHTEST_CHEAT")
        if not cheat_id:
            raise ValueError(
                "No cheat selected. Pass --ak cheat=<id> (e.g. cheat=c02_reward_daemon)."
            )
        self._cheat: Cheat = find_cheat(cheat_id)

    @staticmethod
    def name() -> str:
        return "crashtest"

    def version(self) -> str:
        return f"{self._cheat.meta.id}@{self._cheat.meta.version}"

    async def setup(self, environment: Any) -> None:  # pragma: no cover - needs harbor
        return None

    async def run(
        self, instruction: str, environment: Any, context: Any = None
    ) -> None:  # pragma: no cover - needs harbor
        """Apply the selected cheat to the task environment, then return.

        The reward is produced by the task's verifier afterward, not here.
        """
        agent_dir = self._agent_dir(environment)

        async def _exec(command: str) -> tuple[int, str]:
            result = await environment.exec(command=command)
            return _return_code(result), _stdout(result)

        async def _upload(source_dir: str, target_dir: str) -> None:
            await environment.upload_dir(source_dir=source_dir, target_dir=target_dir)

        await apply_cheat(self._cheat, exec_fn=_exec, upload_fn=_upload, agent_dir=agent_dir)
        return None

    @staticmethod
    def _agent_dir(environment: Any) -> str:  # pragma: no cover - needs harbor
        try:
            from harbor.models.trial.paths import EnvironmentPaths

            return str(EnvironmentPaths.for_os(environment.os).agent_dir)
        except Exception:
            return "/logs/agent"


def _return_code(result: Any) -> int:  # pragma: no cover - needs harbor
    for attr in ("return_code", "returncode", "exit_code", "code"):
        val = getattr(result, attr, None)
        if val is not None:
            return int(val)
    return 0


def _stdout(result: Any) -> str:  # pragma: no cover - needs harbor
    for attr in ("stdout", "output", "text"):
        val = getattr(result, attr, None)
        if val:
            return str(val)
    return ""


__all__ = [
    "CheatAgent",
    "CheatOutcome",
    "apply_cheat",
    "REMOTE_CHEAT_DIR",
    "MARKER_FILENAME",
]
