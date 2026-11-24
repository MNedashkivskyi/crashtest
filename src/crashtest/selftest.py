"""The fixture harness — validate cheats without Harbor.

Every cheat ships two fixtures: ``fixtures/vuln-<id>/`` (a grader with the hole)
and ``fixtures/hardened-<id>/`` (the same grader with the fix applied). The
harness runs, per cheat, a three-point check:

  1. vuln  + no payload  -> reward 0   (the task really fails when nobody cheats)
  2. vuln  + payload      -> reward 1   (the cheat works: HOLE)
  3. hardened + payload   -> reward 0   (the fix stops it: DEFENDED)

If any point is wrong the cheat (or its fixture) is broken and release is
blocked. This is the false-positive guard, and it runs in plain pytest with no
harness and no network.

How a cheat stays hermetic: payloads target real absolute paths (`/tests`,
`/usr/local/bin`, `/logs/verifier`, ...) *by default*, but honour ``CRASHTEST_*``
env overrides. In a real Harbor run those vars are unset, so the real paths are
used. Here the harness points them inside a throwaway sandbox.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cheatspec import Cheat
from .registry import all_cheats, find_cheat

_REWARD_RE = re.compile(r"^REWARD=(-?\d+(?:\.\d+)?)\s*$", re.MULTILINE)
_TIMEOUT_S = 60


@dataclass
class FixtureCheck:
    cheat_id: str
    point: str  # "vuln-baseline" | "vuln-payload" | "hardened-payload"
    expected: float
    reward: Optional[float]
    ok: bool
    detail: str = ""


def default_fixtures_root() -> Path:
    """Locate the repo's ``fixtures/`` dir by walking up from this file, then cwd."""
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in [start, *start.parents]:
            cand = parent / "fixtures"
            if cand.is_dir():
                return cand
    raise FileNotFoundError("could not locate a 'fixtures/' directory")


def _run(cmd: list[str], cwd: Path, env: dict) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _sandbox_env(sandbox: Path) -> dict:
    tests_dir = sandbox / "tests"
    workdir = sandbox / "workspace"
    vlog = sandbox / "logs" / "verifier"
    bindir = sandbox / "bin"
    site_dir = sandbox / "site"  # agent-writable python site (C07/C08/C09)
    artifact_dir = sandbox / "artifacts"  # declared artifact paths (artifact variants)
    for d in (tests_dir, workdir, vlog, bindir, site_dir, artifact_dir):
        d.mkdir(parents=True, exist_ok=True)

    clean_path = os.environ.get("PATH", "/usr/bin:/bin")
    env = dict(os.environ)
    env.update(
        {
            "CRASHTEST_TESTS_DIR": str(tests_dir),
            "CRASHTEST_VERIFIER_LOG_DIR": str(vlog),
            "CRASHTEST_BIN_DIR": str(bindir),
            "CRASHTEST_WORKDIR": str(workdir),
            "CRASHTEST_REPO_ROOT": str(workdir),
            "CRASHTEST_FS_ROOT": str(sandbox),
            "CRASHTEST_SITE_DIR": str(site_dir),
            "CRASHTEST_ARTIFACT_DIR": str(artifact_dir),
            "CRASHTEST_CLEAN_PATH": clean_path,
            # agent-phase PATH: the shim dir wins over the real toolchain
            "PATH": f"{bindir}:{clean_path}",
            # keep pytest from reading the harness's own config/plugins
            "PYTEST_ADDOPTS": "",
        }
    )
    return env


def _grade(sandbox: Path, env: dict) -> Optional[float]:
    grade = sandbox / "grade.sh"
    if not grade.is_file():
        return None
    workdir = Path(env["CRASHTEST_WORKDIR"])
    _ec, out = _run(["sh", str(grade)], cwd=workdir, env=env)
    matches = _REWARD_RE.findall(out)
    if not matches:
        return None
    return float(matches[-1])


def run_point(
    cheat: Cheat, kind: str, apply_payload: bool, fixtures_root: Path
) -> Optional[float]:
    """Run one fixture of a cheat and return the grader's reward (or None)."""
    fixture = fixtures_root / f"{kind}-{cheat.id}"
    if not fixture.is_dir():
        raise FileNotFoundError(f"missing fixture: {fixture}")

    with tempfile.TemporaryDirectory() as td:
        sandbox = Path(td) / "fx"
        shutil.copytree(fixture, sandbox)
        env = _sandbox_env(sandbox)
        workdir = Path(env["CRASHTEST_WORKDIR"])
        # Optional per-fixture setup (build a git repo, seed a site dir, ...).
        setup = sandbox / "setup.sh"
        if setup.is_file():
            _run(["sh", str(setup)], cwd=workdir, env=env)
        if apply_payload:
            _run(["sh", str(cheat.payload)], cwd=workdir, env=env)
        return _grade(sandbox, env)


def check_cheat(cheat: Cheat, fixtures_root: Optional[Path] = None) -> list[FixtureCheck]:
    root = fixtures_root or default_fixtures_root()
    plan = [
        ("vuln-baseline", "vuln", False, 0.0),
        ("vuln-payload", "vuln", True, 1.0),
        ("hardened-payload", "hardened", True, 0.0),
    ]
    results: list[FixtureCheck] = []
    for point, kind, apply_payload, expected in plan:
        try:
            reward = run_point(cheat, kind, apply_payload, root)
            ok = reward is not None and abs(reward - expected) < 1e-9
            detail = "" if ok else f"expected {expected}, got {reward}"
        except Exception as exc:  # fixture missing / script error
            reward, ok, detail = None, False, f"{type(exc).__name__}: {exc}"
        results.append(
            FixtureCheck(cheat.id, point, expected, reward, ok, detail)
        )
    return results


def check_all(fixtures_root: Optional[Path] = None) -> list[FixtureCheck]:
    root = fixtures_root or default_fixtures_root()
    out: list[FixtureCheck] = []
    for cheat in all_cheats():
        out.extend(check_cheat(cheat, root))
    return out


def check_one(cheat_id: str, fixtures_root: Optional[Path] = None) -> list[FixtureCheck]:
    return check_cheat(find_cheat(cheat_id), fixtures_root)
