"""Runner orchestration tests, driven by a fake harness (no Harbor)."""

from dataclasses import dataclass
from typing import Callable, Optional

from crashtest.results import CellVerdict, TaskVerdict, TrialKind, TrialRecord
from crashtest.runner import (
    ScanConfig,
    TaskRef,
    TrialSpec,
    discover_tasks,
    scan_task,
)


@dataclass
class FakeHarness:
    """Returns (reward, applied) for each spec via a supplied function."""

    fn: Callable[[TrialSpec], tuple[Optional[float], Optional[bool]]]

    def run(self, spec: TrialSpec, cfg: ScanConfig) -> TrialRecord:
        reward, applied = self.fn(spec)
        return TrialRecord(
            task_id=spec.task.id,
            dataset=spec.task.dataset,
            kind=spec.kind,
            cheat_id=spec.cheat_id,
            attempt=spec.attempt,
            reward=reward,
            applied=applied,
        )


class _Cheat:
    """Minimal stand-in so scan_task doesn't need the real registry."""

    def __init__(self, cid, defenses=()):
        self.id = cid
        self.meta = type("M", (), {"expected_defense": list(defenses), "fix": f"fix {cid}"})()


TASK = TaskRef(id="t1", dataset="ds")
CFG = ScanConfig()


def _controls_ok(spec):
    if spec.kind == TrialKind.NOP:
        return 0.0, None
    if spec.kind == TrialKind.ORACLE:
        return 1.0, None
    return None, None


def test_valid_controls_hole_and_defended():
    def fn(spec):
        if spec.kind != TrialKind.CHEAT:
            return _controls_ok(spec)
        if spec.cheat_id == "hole":
            return 1.0, True
        return 0.0, True  # defended

    control, cells = scan_task(
        TASK, [_Cheat("hole"), _Cheat("safe")], FakeHarness(fn), CFG
    )
    assert control.verdict == TaskVerdict.VALID
    by = {c.cheat_id: c for c in cells}
    assert by["hole"].verdict == CellVerdict.HOLE
    assert by["hole"].rewards == [1.0, 1.0, 1.0]  # first hit + 2 confirmations
    assert by["safe"].verdict == CellVerdict.DEFENDED
    assert by["safe"].rewards == [0.0]  # no reruns on a miss


def test_broken_oracle_gates_cheats():
    def fn(spec):
        if spec.kind == TrialKind.ORACLE:
            return 0.0, None  # oracle fails
        if spec.kind == TrialKind.NOP:
            return 0.0, None
        return 1.0, True

    control, cells = scan_task(TASK, [_Cheat("hole")], FakeHarness(fn), CFG)
    assert control.verdict == TaskVerdict.BROKEN_ORACLE
    assert cells == []  # gate: cheats not run


def test_not_applicable_cheat():
    def fn(spec):
        if spec.kind != TrialKind.CHEAT:
            return _controls_ok(spec)
        return None, False  # probe said N-A

    _control, cells = scan_task(TASK, [_Cheat("na")], FakeHarness(fn), CFG)
    assert cells[0].verdict == CellVerdict.NA


def test_flaky_hole():
    state = {"n": 0}

    def fn(spec):
        if spec.kind != TrialKind.CHEAT:
            return _controls_ok(spec)
        # first run hits, one rerun misses
        state["n"] += 1
        return (1.0 if state["n"] != 2 else 0.0), True

    _control, cells = scan_task(TASK, [_Cheat("f")], FakeHarness(fn), CFG)
    assert cells[0].verdict == CellVerdict.FLAKY_HOLE


def test_ablation_records_flips():
    def fn(spec):
        if spec.kind != TrialKind.CHEAT:
            return _controls_ok(spec)
        if spec.defense == "separate":
            return 0.0, True  # defense closes it
        return 1.0, True

    cfg = ScanConfig(ablation=True)
    _control, cells = scan_task(
        TASK, [_Cheat("hole", defenses=["separate"])], FakeHarness(fn), cfg
    )
    assert cells[0].verdict == CellVerdict.HOLE
    assert cells[0].defense_flips == {"separate": True}


def test_discover_tasks(tmp_path):
    (tmp_path / "taskA" / "tests").mkdir(parents=True)
    (tmp_path / "taskB").mkdir()
    (tmp_path / "taskB" / "test.sh").write_text("echo hi")
    (tmp_path / "notatask").mkdir()
    tasks = discover_tasks(str(tmp_path))
    ids = sorted(t.id for t in tasks)
    assert ids == ["taskA", "taskB"]


def test_discover_single_task(tmp_path):
    (tmp_path / "solution").mkdir()
    tasks = discover_tasks(str(tmp_path))
    assert len(tasks) == 1 and tasks[0].id == tmp_path.name
