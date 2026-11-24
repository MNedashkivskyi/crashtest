"""No-Docker static hints.

Cheap regex checks over a task's ``test.sh`` and config that correlate with the
dynamic cheats. They need no Docker and no Harbor, so they run in milliseconds and
make a good pre-filter and PR comment. These are intended to be upstreamed as
``harbor lint`` rules; crashtest keeps them only as a fast local hint.

A finding is a *hint*, not a proof — the dynamic scan is the proof. Severities are
advisory.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel


class Finding(BaseModel):
    rule: str
    severity: str  # "warn" | "info"
    message: str
    related_cheats: list[str]
    fix: str
    file: str | None = None
    line: int | None = None


@dataclass
class _Rule:
    id: str
    severity: str
    pattern: re.Pattern
    message: str
    related: list[str]
    fix: str
    # Only fire if this negative pattern is NOT present on the same line/script.
    unless: re.Pattern | None = None
    whole_script: bool = False  # match against the whole file, not per line


_RULES: list[_Rule] = [
    _Rule(
        id="verify-time-download",
        severity="warn",
        pattern=re.compile(r"\b(curl|wget)\b|astral\.sh|\buvx?\b|pip\s+install"),
        message="Toolchain or dependency fetched/installed at verify time; an agent can hijack it.",
        related=["c05_path_shim", "c06_uvx_trojan"],
        fix="Install the verifier toolchain at image build; use an offline, pinned verifier.",
    ),
    _Rule(
        id="pytest-no-isolation",
        severity="warn",
        pattern=re.compile(r"\bpytest\b|\bpy\.test\b"),
        unless=re.compile(r"--noconftest|--confcutdir|--rootdir|PYTEST_DISABLE_PLUGIN_AUTOLOAD"),
        message="pytest invoked without conftest/plugin/rootdir isolation; agent-writable config can hijack it.",
        related=["c03_tests_preplant", "c04_workspace_conftest", "c07_sitecustomize", "c08_pytest_plugin"],
        fix="Run pytest with --noconftest (or --rootdir/--confcutdir) and PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.",
    ),
    _Rule(
        id="pip-install-editable",
        severity="warn",
        pattern=re.compile(r"pip\s+install\s+(-e\s+)?\.|python[0-9.]*\s+setup\.py"),
        message="Verifier builds/installs the agent's repo, executing agent code before tests.",
        related=["c10_build_hook"],
        fix="Install from a pristine copy or at image build; build in a separate verifier.",
    ),
    _Rule(
        id="reward-from-exit-code",
        severity="warn",
        pattern=re.compile(r"pytest[^\n]*(?:&&|\|\||;\s*(?:echo|exit)|\$\?)"),
        unless=re.compile(r"--junitxml|--json|junit|ctrf|report"),
        message="Reward appears to come from the pytest exit code, not a parsed report.",
        related=["c09_exit_injection", "c11_empty_collection"],
        fix="Grade from JUnit/CTRF: require every expected test id present and passed.",
    ),
]


def _iter_script_files(task_dir: Path) -> Iterable[Path]:
    for name in ("test.sh", "run-tests.sh", "verify.sh"):
        p = task_dir / name
        if p.is_file():
            yield p
    tests = task_dir / "tests"
    if tests.is_dir():
        yield from sorted(tests.rglob("*.sh"))


def scan_task_static(task_dir: str) -> list[Finding]:
    """Run the static rules over one task directory."""
    base = Path(task_dir)
    findings: list[Finding] = []

    scripts = list(_iter_script_files(base))
    for script in scripts:
        text = script.read_text(errors="replace")
        rel = str(script.relative_to(base))
        for rule in _RULES:
            if rule.unless and rule.unless.search(text):
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if line.lstrip().startswith("#"):
                    continue
                if rule.pattern.search(line):
                    findings.append(
                        Finding(
                            rule=rule.id,
                            severity=rule.severity,
                            message=rule.message,
                            related_cheats=rule.related,
                            fix=rule.fix,
                            file=rel,
                            line=i,
                        )
                    )
                    break  # one finding per rule per file

    # Leakage hint: a .git shipped with the task.
    if (base / ".git").exists():
        findings.append(
            Finding(
                rule="git-history-shipped",
                severity="info",
                message="Task ships a .git directory; a fix may be reachable from history.",
                related_cheats=["c12_git_mining"],
                fix="Squash at build, drop tags/remotes, expire reflog, git gc --prune=now (or ship no .git).",
                file=".git",
            )
        )
    return findings


def render_findings(findings: list[Finding]) -> str:
    if not findings:
        return "No static hints."
    lines = []
    for f in findings:
        loc = f"{f.file}:{f.line}" if f.line else (f.file or "")
        lines.append(f"[{f.severity}] {f.rule} ({loc}) -> {', '.join(f.related_cheats)}")
        lines.append(f"    {f.message}")
        lines.append(f"    fix: {f.fix}")
    return "\n".join(lines)
