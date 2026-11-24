"""Schema for a cheat's ``cheat.toml`` and a loader for a cheat directory.

A cheat is a directory under ``crashtest/cheats/`` containing:

    cheat.toml   metadata (this schema)
    probe.sh     exit 0 = applies to this task, exit 3 = not applicable
    payload.sh   the actual cheat; runs only when probe said "applies"
    files/       optional payload assets copied alongside the scripts

Entry-point discovery (see registry.py) lets third parties ship extra cheats
without forking crashtest.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

# The defense modes a cheat can be closed by. Used to build the
# defense-attribution matrix in the scorecard.
DEFENSE_MODES = {
    "shared",  # Harbor single-step shared verifier (the weak baseline)
    "separate",  # Harbor separate-verifier mode (fresh sandbox)
    "emptied-dirs",  # NeMo-style: /tests and /logs/verifier emptied before grading
    "task-fix",  # a change to the task's own test.sh / Dockerfile
}

CATEGORIES = {
    "reward-channel",  # writes/forces the reward file or value directly
    "harness-hijack",  # hijacks pytest/conftest/plugins/path
    "toolchain",  # replaces or poisons a tool the verifier downloads/runs
    "exit-code",  # makes the process exit 0 regardless of per-test results
    "leakage",  # the answer ships in the image / is fetchable
    "weak-test",  # the test asserts too little (existence-only, no count)
}

PRIORITIES = {"P0", "P1", "P2"}


class CheatMeta(BaseModel):
    """Parsed ``cheat.toml``."""

    id: str
    version: str
    category: str
    priority: str
    summary: str
    # What a reward of 1 proves about the task's verification.
    proves: str
    # Which defense modes are *expected* to close this cheat. The ablation pass
    # checks these against reality and flags surprises.
    expected_defense: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    fix: str = ""
    false_positive_risk: str = "unknown"
    credit: str | None = None
    # Exit code from probe.sh that means "not applicable to this task".
    na_exit_code: int = 3

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"category {v!r} not in {sorted(CATEGORIES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _prio(cls, v: str) -> str:
        if v not in PRIORITIES:
            raise ValueError(f"priority {v!r} not in {sorted(PRIORITIES)}")
        return v

    @field_validator("expected_defense")
    @classmethod
    def _def(cls, v: list[str]) -> list[str]:
        bad = set(v) - DEFENSE_MODES
        if bad:
            raise ValueError(f"expected_defense {sorted(bad)} not in {sorted(DEFENSE_MODES)}")
        return v


class Cheat(BaseModel):
    """A loaded cheat: metadata plus the paths to its scripts."""

    meta: CheatMeta
    directory: Path
    probe: Path
    payload: Path
    files_dir: Path | None = None

    model_config = {"arbitrary_types_allowed": True}

    @property
    def id(self) -> str:
        return self.meta.id


def load_cheat(directory: Path) -> Cheat:
    """Load and validate a single cheat directory."""
    directory = Path(directory)
    toml_path = directory / "cheat.toml"
    probe = directory / "probe.sh"
    payload = directory / "payload.sh"

    if not toml_path.is_file():
        raise FileNotFoundError(f"{directory}: missing cheat.toml")
    for script in (probe, payload):
        if not script.is_file():
            raise FileNotFoundError(f"{directory}: missing {script.name}")

    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)
    # cheat.toml wraps its fields in a [cheat] table.
    meta = CheatMeta.model_validate(data.get("cheat", data))

    files_dir = directory / "files"
    return Cheat(
        meta=meta,
        directory=directory,
        probe=probe,
        payload=payload,
        files_dir=files_dir if files_dir.is_dir() else None,
    )
