"""The matrix runner.

A thin orchestrator around ``harbor run``: one trial per (task, agent) through
plain ``harbor run``, results parsed from Harbor's trial JSON, then aggregated by
the pure classifiers in :mod:`crashtest.results`.

The orchestration (controls -> validity gate -> per-cheat cells -> confirmation
reruns -> optional ablation) is a pure function of a ``Harness``. The real
``harbor``-driving harness and a test fake both satisfy that interface, so the
whole control flow is unit-tested with no Harbor and no network.

Harbor writes each run to ``jobs/<timestamp>/result.json``, with per-task rewards
under ``stats.evals[<agent>__<dataset>].reward_stats.reward`` (a map from reward
value to the list of task ids that scored it). ``parse_result_json`` reads that
shape. Two scan paths exist: dataset mode (``scan_dataset``) runs a whole Harbor
dataset per agent/cheat and reads every task's reward from one ``result.json`` —
this is what a registry dataset needs, since its tasks have no local paths; path
mode (``run_scan``) drives one task directory at a time and is what the CI Action
uses on a task repo. Both feed the same pure classifiers in
:mod:`crashtest.results`.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .cheatspec import Cheat
from .registry import all_cheats
from .results import (
    CellResult,
    CellVerdict,
    TaskControl,
    TaskVerdict,
    TrialKind,
    TrialRecord,
    classify_cell,
    classify_controls,
)

# Task markers used to recognise a task directory when scanning a path.
_TASK_MARKERS = ("tests", "solution", "task.toml", "task.yaml", "environment", "test.sh")


@dataclass
class TaskRef:
    id: str
    dataset: str = ""
    path: str | None = None
    git_commit: str | None = None


@dataclass
class TrialSpec:
    task: TaskRef
    kind: TrialKind
    cheat_id: str | None = None
    attempt: int = 0
    defense: str | None = None  # ablation: run with this defense mode applied


@dataclass
class ScanConfig:
    control_repeats: int = 3
    confirm_reruns: int = 2  # extra runs after a first hit (total 3)
    harbor_bin: str = "harbor"
    nop_agent: str = "nop"
    oracle_agent: str = "oracle"
    cheat_agent: str = "crashtest.agent:CheatAgent"
    # None => let harbor use its own default (currently 4). Set to match vCPUs.
    n_concurrent: int | None = None
    agent_timeout_multiplier: float | None = None
    timeout_multiplier: float | None = None
    # Determinism pins, copied into every record and the scorecard header.
    harbor_commit: str | None = None
    dataset_commit: str | None = None
    image_digest: str | None = None
    ablation: bool = False
    output_root: str | None = None
    dry_run: bool = False


class Harness(Protocol):
    """Runs one trial and returns its record."""

    def run(self, spec: TrialSpec, cfg: ScanConfig) -> TrialRecord: ...


# --- task discovery ---------------------------------------------------------


def _looks_like_task(d: Path) -> bool:
    return any((d / m).exists() for m in _TASK_MARKERS)


def discover_tasks(path: str, dataset: str = "") -> list[TaskRef]:
    """Find tasks under a path: the path itself if it is a task, else its children."""
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(path)
    if _looks_like_task(root):
        return [TaskRef(id=root.name, dataset=dataset or root.name, path=str(root))]
    tasks: list[TaskRef] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and _looks_like_task(child):
            tasks.append(TaskRef(id=child.name, dataset=dataset or root.name, path=str(child)))
    return tasks


# --- parsing Harbor's result.json -------------------------------------------

JOBS_ROOT = "jobs"

# Harbor prints this on every run; it is the reliable way to find *this* run's
# output (mtime-based guessing races when runs overlap or the file is written
# incrementally).
_RESULT_PATH_RE = re.compile(r"Results written to (\S+result\.json)")


def result_path_from_output(text: str) -> str | None:
    """Pull the ``Results written to <path>`` line out of harbor's stdout/stderr."""
    matches = _RESULT_PATH_RE.findall(text or "")
    return matches[-1] if matches else None


def _run_complete(path: str | Path) -> bool:
    """True if a result.json is a finished run (no trials still running)."""
    try:
        data = json.loads(Path(path).read_text())
    except Exception:
        return False
    stats = data.get("stats") or {}
    return data.get("finished_at") is not None and not stats.get("n_running_trials")


def _base_task_id(task_id: str) -> str:
    """Strip Harbor's per-instance suffix: ``chess-best-move__x8Vc2Kd`` -> ``chess-best-move``."""
    return task_id.split("__", 1)[0]


def parse_result_json(path: str | Path) -> dict[str, float | None]:
    """Map base task id -> reward from a Harbor ``result.json``.

    Rewards live under ``stats.evals[*].reward_stats.reward`` as a map from the
    reward value (a string like ``"1.0"``) to the list of task ids that scored it.
    A task that errored is absent from every bucket and simply does not appear.
    """
    data = json.loads(Path(path).read_text())
    out: dict[str, float | None] = {}
    evals = (data.get("stats") or {}).get("evals") or {}
    for ev in evals.values():
        reward_map = ((ev.get("reward_stats") or {}).get("reward")) or {}
        for value, ids in reward_map.items():
            try:
                reward = float(value)
            except (TypeError, ValueError):
                reward = None
            for task_id in ids or []:
                out[_base_task_id(task_id)] = reward
    return out


# --- the real, harbor-driving harness --------------------------------------


class HarborHarness:
    """Drives ``harbor run`` and reads rewards from its ``result.json``."""

    def __init__(self, jobs_root: str = JOBS_ROOT):
        self.jobs_root = jobs_root

    # -- path mode: one task directory per call (CI Action on a task repo) --

    def run(self, spec: TrialSpec, cfg: ScanConfig) -> TrialRecord:
        started = datetime.now(UTC)
        cmd = self.build_command(spec, cfg)
        if cfg.dry_run:
            return TrialRecord(
                task_id=spec.task.id,
                dataset=spec.task.dataset,
                kind=spec.kind,
                cheat_id=spec.cheat_id,
                attempt=spec.attempt,
                reward=None,
                notes="dry-run: " + " ".join(shlex.quote(c) for c in cmd),
                started_at=started,
                finished_at=datetime.now(UTC),
            )
        errored = False
        timed_out = False
        output = ""
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            timed_out = True
        except Exception:
            errored = True

        reward: float | None = None
        raw_path: str | None = None
        if not errored and not timed_out:
            try:
                raw_path = self._result_path(output)
                per_task = parse_result_json(raw_path) if raw_path else {}
                reward = per_task.get(spec.task.id)
                if reward is None and len(per_task) == 1:
                    reward = next(iter(per_task.values()))
                if raw_path is None:
                    errored = True  # could not locate this run's output
            except Exception:
                errored = True

        return TrialRecord(
            task_id=spec.task.id,
            dataset=spec.task.dataset,
            kind=spec.kind,
            cheat_id=spec.cheat_id,
            attempt=spec.attempt,
            reward=reward,
            errored=errored,
            timed_out=timed_out,
            harbor_commit=cfg.harbor_commit,
            dataset_commit=cfg.dataset_commit,
            image_digest=cfg.image_digest,
            started_at=started,
            finished_at=datetime.now(UTC),
            raw_trial_path=raw_path,
        )

    def build_command(self, spec: TrialSpec, cfg: ScanConfig) -> list[str]:
        cmd = [cfg.harbor_bin, "run"]
        cmd += self._agent_args(spec.kind, spec.cheat_id, cfg)
        if spec.task.path:
            cmd += ["-p", spec.task.path]
        elif spec.task.dataset:
            cmd += ["--dataset", spec.task.dataset]
        if spec.task.git_commit:
            cmd += ["--task-git-commit", spec.task.git_commit]
        if cfg.agent_timeout_multiplier is not None:
            cmd += ["--agent-timeout-multiplier", str(cfg.agent_timeout_multiplier)]
        return cmd

    # -- dataset mode: one whole Harbor dataset per call (registry datasets) --

    def build_dataset_command(
        self, kind: TrialKind, cheat_id: str | None, dataset: str, cfg: ScanConfig
    ) -> list[str]:
        cmd = [cfg.harbor_bin, "run"]
        cmd += self._agent_args(kind, cheat_id, cfg)
        cmd += ["--dataset", dataset]
        if cfg.n_concurrent is not None:
            cmd += ["--n-concurrent", str(cfg.n_concurrent)]
        if cfg.timeout_multiplier is not None:
            cmd += ["--timeout-multiplier", str(cfg.timeout_multiplier)]
        if cfg.agent_timeout_multiplier is not None:
            cmd += ["--agent-timeout-multiplier", str(cfg.agent_timeout_multiplier)]
        return cmd

    def run_dataset(
        self, kind: TrialKind, cheat_id: str | None, dataset: str, cfg: ScanConfig
    ) -> dict[str, float | None]:
        """Run one agent/cheat over a whole dataset; return {task id -> reward}."""
        cmd = self.build_dataset_command(kind, cheat_id, dataset, cfg)
        if cfg.dry_run:
            print("dry-run: " + " ".join(shlex.quote(c) for c in cmd))
            return {}
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
            output = (proc.stdout or "") + (proc.stderr or "")
        except Exception:
            return {}
        raw = self._result_path(output)
        return parse_result_json(raw) if raw else {}

    def _result_path(self, output: str) -> str | None:
        """The result.json for the run that just finished.

        ONLY the exact path harbor printed ("Results written to ..."). There is
        deliberately no newest-file fallback: when a run produces no output of its
        own (e.g. the agent failed to execute), reading some other run's result
        manufactures false verdicts. No printed path => treat the run as failed
        (reward None => the cell becomes ERROR, never a HOLE).
        """
        path = result_path_from_output(output)
        if path and Path(path).is_file():
            return path
        return None

    @staticmethod
    def _agent_args(kind: TrialKind, cheat_id: str | None, cfg: ScanConfig) -> list[str]:
        if kind == TrialKind.NOP:
            return ["-a", cfg.nop_agent]
        if kind == TrialKind.ORACLE:
            return ["-a", cfg.oracle_agent]
        return ["-a", cfg.cheat_agent, "--ak", f"cheat={cheat_id}"]


# --- the pure orchestration -------------------------------------------------


def scan_task(
    task: TaskRef, cheats: list[Cheat], harness: Harness, cfg: ScanConfig
) -> tuple[TaskControl, list[CellResult]]:
    """Run controls then cheats for one task. Cheats run only if controls pass."""
    nop = [
        harness.run(TrialSpec(task, TrialKind.NOP, attempt=i), cfg)
        for i in range(cfg.control_repeats)
    ]
    oracle = [
        harness.run(TrialSpec(task, TrialKind.ORACLE, attempt=i), cfg)
        for i in range(cfg.control_repeats)
    ]
    nop_rewards = [r.reward for r in nop]
    oracle_rewards = [r.reward for r in oracle]
    verdict = classify_controls(nop_rewards, oracle_rewards)
    control = TaskControl(
        task_id=task.id,
        dataset=task.dataset,
        verdict=verdict,
        nop_rewards=nop_rewards,
        oracle_rewards=oracle_rewards,
    )

    cells: list[CellResult] = []
    if verdict != TaskVerdict.VALID:
        return control, cells  # validity gate

    for cheat in cheats:
        first = harness.run(TrialSpec(task, TrialKind.CHEAT, cheat_id=cheat.id, attempt=0), cfg)
        rewards = [first.reward]
        applied = first.applied
        errored = first.errored
        timed_out = first.timed_out

        if applied is False:
            cells.append(
                CellResult(
                    task_id=task.id,
                    dataset=task.dataset,
                    cheat_id=cheat.id,
                    verdict=CellVerdict.NA,
                    rewards=rewards,
                    applied=False,
                )
            )
            continue

        if first.scored_one:
            for i in range(cfg.confirm_reruns):
                r = harness.run(
                    TrialSpec(task, TrialKind.CHEAT, cheat_id=cheat.id, attempt=1 + i), cfg
                )
                rewards.append(r.reward)
                errored = errored or r.errored
                timed_out = timed_out or r.timed_out

        cell_verdict = classify_cell(
            rewards, applied=applied, errored=errored, timed_out=timed_out
        )
        cell = CellResult(
            task_id=task.id,
            dataset=task.dataset,
            cheat_id=cheat.id,
            verdict=cell_verdict,
            rewards=rewards,
            applied=applied if applied is not None else True,
        )
        if cfg.ablation and cell_verdict == CellVerdict.HOLE:
            cell.defense_flips = _ablate(task, cheat, harness, cfg)
        cells.append(cell)

    return control, cells


def _ablate(task: TaskRef, cheat: Cheat, harness: Harness, cfg: ScanConfig) -> dict[str, bool]:
    """Rerun a HOLE under each expected defense; True = the hole flipped to 0."""
    flips: dict[str, bool] = {}
    for mode in cheat.meta.expected_defense:
        r = harness.run(
            TrialSpec(task, TrialKind.CHEAT, cheat_id=cheat.id, attempt=99, defense=mode), cfg
        )
        flips[mode] = not r.scored_one
    return flips


def run_scan(
    tasks: list[TaskRef],
    cheats: list[Cheat] | None,
    harness: Harness,
    cfg: ScanConfig,
) -> tuple[list[TaskControl], list[CellResult]]:
    cheats = cheats if cheats is not None else all_cheats()
    controls: list[TaskControl] = []
    cells: list[CellResult] = []
    for task in tasks:
        control, task_cells = scan_task(task, cheats, harness, cfg)
        controls.append(control)
        cells.extend(task_cells)
    return controls, cells


class DatasetHarness(Protocol):
    """Runs one agent/cheat over a whole dataset and returns {task id -> reward}."""

    def run_dataset(
        self, kind: TrialKind, cheat_id: str | None, dataset: str, cfg: ScanConfig
    ) -> dict[str, float | None]: ...


def _scored_one(reward: float | None) -> bool:
    return reward is not None and reward >= 1.0


def scan_dataset(
    dataset: str,
    cheats: list[Cheat] | None,
    harness: DatasetHarness,
    cfg: ScanConfig,
    *,
    on_update: Callable[[list[TaskControl], list[CellResult]], None] | None = None,
    resume_controls: list[TaskControl] | None = None,
    resume_cells: list[CellResult] | None = None,
) -> tuple[list[TaskControl], list[CellResult]]:
    """Scan every task in a Harbor dataset.

    One Harbor run per agent/cheat (not per task): controls are run
    ``control_repeats`` times, then each cheat once over the whole dataset, with
    ``confirm_reruns`` more full-dataset runs only if any valid task was hit.
    Per-task rewards come from each run's ``result.json``.

    ``on_update`` is called after controls and after each cheat with the results
    so far, so the caller can flush a scorecard incrementally (a crash mid-run
    then keeps everything already computed). ``resume_controls``/``resume_cells``
    let a restart skip the controls and any cheats already done.
    """
    cheats = cheats if cheats is not None else all_cheats()

    # --- resume: reuse prior controls, skip already-done cheats ---
    if resume_controls is not None:
        controls = list(resume_controls)
        valid = [c.task_id for c in controls if c.verdict == TaskVerdict.VALID]
    else:
        nop_runs = [
            harness.run_dataset(TrialKind.NOP, None, dataset, cfg)
            for _ in range(cfg.control_repeats)
        ]
        oracle_runs = [
            harness.run_dataset(TrialKind.ORACLE, None, dataset, cfg)
            for _ in range(cfg.control_repeats)
        ]
        task_ids: set[str] = set()
        for run in nop_runs + oracle_runs:
            task_ids.update(run)
        controls = []
        valid = []
        for task_id in sorted(task_ids):
            nop_rewards = [run.get(task_id) for run in nop_runs]
            oracle_rewards = [run.get(task_id) for run in oracle_runs]
            verdict = classify_controls(nop_rewards, oracle_rewards)
            controls.append(
                TaskControl(
                    task_id=task_id,
                    dataset=dataset,
                    verdict=verdict,
                    nop_rewards=nop_rewards,
                    oracle_rewards=oracle_rewards,
                )
            )
            if verdict == TaskVerdict.VALID:
                valid.append(task_id)

    cells: list[CellResult] = list(resume_cells or [])
    done_cheat_ids = {c.cheat_id for c in cells}
    if on_update is not None:
        on_update(controls, cells)

    for cheat in cheats:
        if cheat.id in done_cheat_ids:
            continue  # already computed in a previous (resumed) run
        runs = [harness.run_dataset(TrialKind.CHEAT, cheat.id, dataset, cfg)]
        # Confirm only if the cheat hit a valid task on the first pass. A rerun
        # re-runs the whole dataset, so every task then has the full reward list.
        if any(_scored_one(runs[0].get(t)) for t in valid):
            for _ in range(cfg.confirm_reruns):
                runs.append(harness.run_dataset(TrialKind.CHEAT, cheat.id, dataset, cfg))
        for task_id in valid:
            rewards = [run.get(task_id) for run in runs]
            cells.append(
                CellResult(
                    task_id=task_id,
                    dataset=dataset,
                    cheat_id=cheat.id,
                    verdict=classify_cell(rewards, applied=True),
                    rewards=rewards,
                    applied=True,
                )
            )
        if on_update is not None:
            on_update(controls, cells)  # flush after each cheat

    return controls, cells


def collect_pins(cfg: ScanConfig) -> dict[str, str | None]:
    """Best-effort determinism pins for the scorecard header."""
    harbor_commit = cfg.harbor_commit
    if harbor_commit is None:
        try:
            out = subprocess.run(
                [cfg.harbor_bin, "--version"], capture_output=True, text=True, timeout=10
            )
            harbor_commit = (out.stdout or out.stderr).strip() or None
        except Exception:
            harbor_commit = None
    return {
        "harbor": harbor_commit,
        "dataset_commit": cfg.dataset_commit,
        "image_digest": cfg.image_digest,
    }
