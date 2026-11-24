"""Result model and verdict classification.

Pure, Harbor-free data types plus the two classification functions that turn raw
per-trial rewards into task and cell verdicts. Keeping classification here (and
not in the runner) means the rules are unit-testable without any harness.

Vocabulary (from the spec):
  * A *trial* is one fresh run of one agent (nop / oracle / a cheat) on one task.
  * The two *controls* are the nop agent (must score 0) and the oracle agent
    (must score 1). A task is only VALID if both controls behave.
  * A *cell* is one (task x cheat) pair. A cheat runs once; a reward of 1 on
    that first run triggers 2 reruns, so a hit is confirmed 3/3.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrialKind(str, enum.Enum):
    NOP = "nop"
    ORACLE = "oracle"
    CHEAT = "cheat"


class TaskVerdict(str, enum.Enum):
    """Whether a task's controls behave well enough to trust its cheat cells."""

    VALID = "VALID"
    BROKEN_ORACLE = "BROKEN-ORACLE"  # oracle does not reliably score 1
    BROKEN_NOP = "BROKEN-NOP"  # no-op reliably scores 1 (grader passes nothing)
    FLAKY_CONTROL = "FLAKY-CONTROL"  # a control is inconsistent across repeats


class CellVerdict(str, enum.Enum):
    """Outcome of one cheat against one task."""

    HOLE = "HOLE"  # cheat scored 1 on all 3 confirmation runs
    FLAKY_HOLE = "FLAKY-HOLE"  # cheat scored 1 on 1-2 of 3 runs
    DEFENDED = "DEFENDED"  # cheat never scored 1
    NA = "N-A"  # cheat's probe said it does not apply to this task
    ERROR = "ERROR"  # trial errored or timed out; never counted as DEFENDED


class TrialRecord(BaseModel):
    """One trial: one agent run on one task, with the grader's reward."""

    task_id: str
    dataset: str
    kind: TrialKind
    cheat_id: Optional[str] = None
    attempt: int = 0  # 0-based index within this cell/control

    # None reward means the grader produced no parseable reward (treated as error).
    reward: Optional[float] = None
    applied: Optional[bool] = None  # cheat probe result; None for controls
    errored: bool = False
    timed_out: bool = False
    duration_s: Optional[float] = None

    # Determinism pins, copied into every record and the scorecard header.
    harbor_commit: Optional[str] = None
    dataset_commit: Optional[str] = None
    image_digest: Optional[str] = None

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    raw_trial_path: Optional[str] = None  # path to Harbor's own trial JSON
    notes: Optional[str] = None

    @property
    def scored_one(self) -> bool:
        return self.reward is not None and self.reward >= 1.0 and not self.errored


class TaskControl(BaseModel):
    """Aggregated control outcome for one task."""

    task_id: str
    dataset: str
    verdict: TaskVerdict
    nop_rewards: list[Optional[float]] = Field(default_factory=list)
    oracle_rewards: list[Optional[float]] = Field(default_factory=list)


class CellResult(BaseModel):
    """Aggregated (task x cheat) outcome."""

    task_id: str
    dataset: str
    cheat_id: str
    verdict: CellVerdict
    rewards: list[Optional[float]] = Field(default_factory=list)
    applied: Optional[bool] = None
    # Set by the ablation pass: does the matching defense flip this HOLE to 0?
    defense_flips: Optional[dict[str, bool]] = None


def _is_one(r: Optional[float]) -> bool:
    return r is not None and r >= 1.0


def _is_zero(r: Optional[float]) -> bool:
    return r is not None and r < 1.0


def classify_controls(
    nop_rewards: list[Optional[float]],
    oracle_rewards: list[Optional[float]],
) -> TaskVerdict:
    """Classify a task from its control rewards.

    VALID requires every nop run == 0 and every oracle run == 1. Anything else is
    BROKEN (consistently wrong) or FLAKY-CONTROL (inconsistent across repeats).
    A control with an unparseable/None reward is treated as inconsistent.
    """
    if not nop_rewards or not oracle_rewards:
        return TaskVerdict.FLAKY_CONTROL

    nop_all_zero = all(_is_zero(r) for r in nop_rewards)
    oracle_all_one = all(_is_one(r) for r in oracle_rewards)
    if nop_all_zero and oracle_all_one:
        return TaskVerdict.VALID

    nop_all_one = all(_is_one(r) for r in nop_rewards)
    oracle_all_zero = all(_is_zero(r) for r in oracle_rewards)

    # Inconsistent within a control set => flaky (reported as its own number).
    nop_flaky = not nop_all_zero and not nop_all_one
    oracle_flaky = not oracle_all_one and not oracle_all_zero
    if nop_flaky or oracle_flaky:
        return TaskVerdict.FLAKY_CONTROL

    # Consistent but wrong.
    if nop_all_one:
        return TaskVerdict.BROKEN_NOP
    if oracle_all_zero:
        return TaskVerdict.BROKEN_ORACLE

    # e.g. nop all zero but oracle neither all-one nor all-zero is caught above;
    # any remaining mix is flaky.
    return TaskVerdict.FLAKY_CONTROL


def classify_cell(
    rewards: list[Optional[float]],
    *,
    applied: Optional[bool],
    errored: bool = False,
    timed_out: bool = False,
) -> CellVerdict:
    """Classify a cheat cell from its reward sequence.

    The runner records 1 reward when the first run scores 0 (DEFENDED) and 3 when
    the first run scores 1 (so the hit is confirmed). Precedence: N-A, then ERROR,
    then the reward counts.
    """
    if applied is False:
        return CellVerdict.NA

    valid = [r for r in rewards if r is not None]
    if not valid:
        return CellVerdict.ERROR

    ones = sum(1 for r in rewards if _is_one(r))
    n = len(rewards)

    # A timeout or error with no clean 3/3 or 0/n signal is ERROR, never DEFENDED.
    if (timed_out or errored) and not (ones == 0 or (n >= 3 and ones == n)):
        return CellVerdict.ERROR

    if ones == 0:
        return CellVerdict.DEFENDED
    if n >= 3 and ones == n:
        return CellVerdict.HOLE
    return CellVerdict.FLAKY_HOLE
