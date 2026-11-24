"""The matrix runner.

A thin orchestrator around ``harbor run``: one trial per (task, agent) through
plain ``harbor run``, results parsed from Harbor's trial JSON, then aggregated by
the pure classifiers in :mod:`crashtest.results`.

The orchestration (controls -> validity gate -> per-cheat cells -> confirmation
reruns -> optional ablation) is a pure function of a ``Harness``. The real
``harbor``-driving harness and a test fake both satisfy that interface, so the
whole control flow is unit-tested with no Harbor and no network.

WEEK-1 / unverified (see docs/open-questions.md): the exact ``harbor run`` output
layout and the trial JSON path. Those live only in ``HarborHarness`` and are
isolated behind small methods so they can be pinned without touching the
orchestration.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
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
    n_concurrent: int = 1
    agent_timeout_multiplier: float | None = None
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


# --- the real, harbor-driving harness --------------------------------------


class HarborHarness:
    """Drives ``harbor run`` and parses the trial reward.

    The command construction, job-dir discovery and reward extraction are the
    only Harbor-coupled parts; each is a small method to pin in week 1.
    """

    def run(self, spec: TrialSpec, cfg: ScanConfig) -> TrialRecord:
        started = datetime.now(UTC)
        cmd, out_dir = self.build_command(spec, cfg)
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
        try:
            subprocess.run(cmd, check=False, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            timed_out = True
        except Exception:
            errored = True

        reward: float | None = None
        applied: bool | None = None
        raw_path: str | None = None
        if not errored and not timed_out:
            try:
                raw_path = self.find_trial_json(out_dir)
                reward = self.extract_reward(raw_path) if raw_path else None
                applied = self.extract_applied(out_dir) if spec.kind == TrialKind.CHEAT else None
            except Exception:
                errored = True

        return TrialRecord(
            task_id=spec.task.id,
            dataset=spec.task.dataset,
            kind=spec.kind,
            cheat_id=spec.cheat_id,
            attempt=spec.attempt,
            reward=reward,
            applied=applied,
            errored=errored,
            timed_out=timed_out,
            harbor_commit=cfg.harbor_commit,
            dataset_commit=cfg.dataset_commit,
            image_digest=cfg.image_digest,
            started_at=started,
            finished_at=datetime.now(UTC),
            raw_trial_path=raw_path,
        )

    # -- the seams to pin in week 1 --

    def build_command(self, spec: TrialSpec, cfg: ScanConfig) -> tuple[list[str], str]:
        out_dir = os.path.join(
            cfg.output_root or ".crashtest-jobs",
            f"{spec.task.id}.{spec.kind.value}.{spec.cheat_id or 'control'}.{spec.attempt}",
        )
        cmd = [cfg.harbor_bin, "run"]
        if spec.kind == TrialKind.NOP:
            cmd += ["-a", cfg.nop_agent]
        elif spec.kind == TrialKind.ORACLE:
            cmd += ["-a", cfg.oracle_agent]
        else:
            cmd += ["-a", cfg.cheat_agent, "--ak", f"cheat={spec.cheat_id}"]
        if spec.task.path:
            cmd += ["-p", spec.task.path]
        elif spec.task.dataset:
            cmd += ["--dataset", spec.task.dataset]
        if spec.task.git_commit:
            cmd += ["--task-git-commit", spec.task.git_commit]
        if cfg.agent_timeout_multiplier is not None:
            cmd += ["--agent-timeout-multiplier", str(cfg.agent_timeout_multiplier)]
        cmd += ["--include-task-name", spec.task.id]
        # Output flag name is unverified; pass a best-effort -o and also record
        # out_dir so find_trial_json can look there or fall back to latest.
        cmd += ["-o", out_dir]
        return cmd, out_dir

    def find_trial_json(self, out_dir: str) -> str | None:
        base = Path(out_dir)
        if not base.exists():
            return None
        # Harbor's exact filename is unverified; pick the newest *.json that
        # parses as a trial result.
        candidates = sorted(base.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0]) if candidates else None

    def extract_reward(self, trial_json_path: str) -> float | None:
        data = json.loads(Path(trial_json_path).read_text())
        # Try the documented shapes in order.
        for key in ("reward", "score", "result"):
            if isinstance(data, dict) and key in data:
                val = data[key]
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, dict) and "reward" in val:
                    return float(val["reward"])
        return None

    def extract_applied(self, out_dir: str) -> bool | None:
        # Read crashtest's own manifest if Harbor surfaced it in the job dir.
        for man in Path(out_dir).rglob("crashtest.json"):
            try:
                return bool(json.loads(man.read_text()).get("applied"))
            except Exception:
                continue
        return None


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
