"""Runner orchestration tests, driven by a fake harness (no Harbor)."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from crashtest.results import CellVerdict, TaskVerdict, TrialKind, TrialRecord
from crashtest.runner import (
    ScanConfig,
    TaskRef,
    TrialSpec,
    discover_tasks,
    parse_result_json,
    scan_dataset,
    scan_task,
)


@dataclass
class FakeHarness:
    """Returns (reward, applied) for each spec via a supplied function."""

    fn: Callable[[TrialSpec], tuple[float | None, bool | None]]

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


# --- dataset mode -----------------------------------------------------------


def test_parse_result_json(tmp_path):
    # mirrors the shape Harbor actually writes
    doc = {
        "stats": {
            "evals": {
                "oracle__terminal-bench-sample": {
                    "metrics": [{"mean": 0.7}],
                    "reward_stats": {
                        "reward": {
                            "1.0": ["chess-best-move__x8Vc2Kd", "regex-log__uHpw8q7"],
                            "0.0": ["qemu-startup__vX4KMTy"],
                        }
                    },
                }
            }
        }
    }
    p = tmp_path / "result.json"
    p.write_text(json.dumps(doc))
    per = parse_result_json(p)
    assert per == {"chess-best-move": 1.0, "regex-log": 1.0, "qemu-startup": 0.0}


class FakeDatasetHarness:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def run_dataset(self, kind, cheat_id, dataset, cfg):
        self.calls.append((kind, cheat_id))
        return self.fn(kind, cheat_id)


def _dataset_fn(kind, cheat_id):
    if kind == TrialKind.NOP:
        return {"t1": 0.0, "t2": 0.0}
    if kind == TrialKind.ORACLE:
        return {"t1": 1.0, "t2": 0.0}  # t1 valid, t2 broken-oracle
    if cheat_id == "hole":
        return {"t1": 1.0, "t2": 1.0}
    return {"t1": 0.0, "t2": 0.0}  # "safe"


def test_scan_dataset_gating_and_verdicts():
    controls, cells = scan_dataset(
        "ds", [_Cheat("hole"), _Cheat("safe")], FakeDatasetHarness(_dataset_fn), ScanConfig()
    )
    cmap = {c.task_id: c.verdict for c in controls}
    assert cmap["t1"] == TaskVerdict.VALID
    assert cmap["t2"] == TaskVerdict.BROKEN_ORACLE

    # only the valid task gets cells
    assert {c.task_id for c in cells} == {"t1"}
    by = {c.cheat_id: c for c in cells}
    assert by["hole"].verdict == CellVerdict.HOLE
    assert by["hole"].rewards == [1.0, 1.0, 1.0]
    assert by["safe"].verdict == CellVerdict.DEFENDED
    assert by["safe"].rewards == [0.0]  # no reruns when nothing hit


def test_scan_dataset_skips_reruns_when_defended():
    h = FakeDatasetHarness(_dataset_fn)
    scan_dataset("ds", [_Cheat("safe")], h, ScanConfig())
    cheat_calls = [c for c in h.calls if c[0] == TrialKind.CHEAT]
    assert cheat_calls == [(TrialKind.CHEAT, "safe")]  # ran once, no confirmation reruns


def test_result_path_from_output():
    from crashtest.runner import result_path_from_output

    out = (
        "  10/10 Mean: 0.700\n"
        "Job Info\n"
        "Total runtime: 3m 22s\n"
        "Results written to jobs/2026-11-24__17-42-45/result.json\n"
        "Inspect results by running `harbor view jobs`\n"
    )
    assert result_path_from_output(out) == "jobs/2026-11-24__17-42-45/result.json"
    assert result_path_from_output("no path here") is None


def test_run_complete(tmp_path):
    from crashtest.runner import _run_complete

    done = tmp_path / "done.json"
    done.write_text(json.dumps({"finished_at": "2026-11-24T18:00:00", "stats": {"n_running_trials": 0}}))
    running = tmp_path / "running.json"
    running.write_text(json.dumps({"finished_at": None, "stats": {"n_running_trials": 4}}))
    assert _run_complete(done) is True
    assert _run_complete(running) is False
