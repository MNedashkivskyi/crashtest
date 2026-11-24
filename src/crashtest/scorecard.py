"""Scorecard: turn controls + cells into scorecard.json, scorecard.md and SARIF.

The markdown is the human artifact: a determinism header, a controls summary, the
task x cheat matrix, and a per-task fix list (every HOLE with its cheat's fix
text). The JSON is the machine record (versioned schema). SARIF drives GitHub
code-scanning annotations from the Action.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .registry import all_cheats
from .results import CellResult, CellVerdict, TaskControl, TaskVerdict

SCHEMA_VERSION = "1.0"

_CELL_SYMBOL = {
    CellVerdict.HOLE: "HOLE",
    CellVerdict.FLAKY_HOLE: "flaky",
    CellVerdict.DEFENDED: "ok",
    CellVerdict.NA: "-",
    CellVerdict.ERROR: "err",
}


class Scorecard(BaseModel):
    schema_version: str = SCHEMA_VERSION
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pins: dict[str, str | None] = Field(default_factory=dict)
    config: dict[str, object] = Field(default_factory=dict)
    controls: list[TaskControl] = Field(default_factory=list)
    cells: list[CellResult] = Field(default_factory=list)

    # -- summaries --

    def control_counts(self) -> dict[str, int]:
        counts = {v.value: 0 for v in TaskVerdict}
        for c in self.controls:
            counts[c.verdict.value] += 1
        return counts

    def valid_task_ids(self) -> list[str]:
        return [c.task_id for c in self.controls if c.verdict == TaskVerdict.VALID]

    def cell_counts(self) -> dict[str, int]:
        counts = {v.value: 0 for v in CellVerdict}
        for cell in self.cells:
            counts[cell.verdict.value] += 1
        return counts

    def holes(self) -> list[CellResult]:
        return [c for c in self.cells if c.verdict in (CellVerdict.HOLE, CellVerdict.FLAKY_HOLE)]

    def tasks_with_hole(self) -> list[str]:
        return sorted({c.task_id for c in self.cells if c.verdict == CellVerdict.HOLE})


def build_scorecard(
    controls: list[TaskControl],
    cells: list[CellResult],
    *,
    pins: dict | None = None,
    config: dict | None = None,
) -> Scorecard:
    return Scorecard(
        pins=pins or {},
        config=config or {},
        controls=list(controls),
        cells=list(cells),
    )


def _fix_text() -> dict[str, str]:
    return {c.id: c.meta.fix for c in all_cheats()}


def render_markdown(sc: Scorecard) -> str:
    lines: list[str] = []
    lines.append("# crashtest scorecard")
    lines.append("")
    lines.append(f"- schema: {sc.schema_version}")
    lines.append(f"- generated: {sc.generated_at.isoformat()}")
    for k, v in sc.pins.items():
        lines.append(f"- {k}: `{v}`")
    for k, v in sc.config.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")

    # Controls
    cc = sc.control_counts()
    lines.append("## Controls")
    lines.append("")
    lines.append(
        f"VALID {cc['VALID']} · BROKEN-ORACLE {cc['BROKEN-ORACLE']} · "
        f"BROKEN-NOP {cc['BROKEN-NOP']} · FLAKY-CONTROL {cc['FLAKY-CONTROL']}"
    )
    lines.append("")

    valid = sc.valid_task_ids()
    cheat_ids = sorted({c.cheat_id for c in sc.cells})

    # Matrix
    lines.append("## Matrix (valid tasks x cheats)")
    lines.append("")
    if not valid or not cheat_ids:
        lines.append("_No valid tasks with cheat cells._")
    else:
        by = {(c.task_id, c.cheat_id): c for c in sc.cells}
        header = "| task | " + " | ".join(cheat_ids) + " |"
        sep = "| --- | " + " | ".join("---" for _ in cheat_ids) + " |"
        lines.append(header)
        lines.append(sep)
        for task_id in valid:
            row = [task_id]
            for ch in cheat_ids:
                cell = by.get((task_id, ch))
                row.append(_CELL_SYMBOL[cell.verdict] if cell else "")
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Fix list
    holes = sc.holes()
    lines.append("## Holes and fixes")
    lines.append("")
    if not holes:
        lines.append("_No holes found._")
    else:
        fixes = _fix_text()
        per_task: dict[str, list[CellResult]] = {}
        for h in holes:
            per_task.setdefault(h.task_id, []).append(h)
        for task_id, hs in sorted(per_task.items()):
            lines.append(f"### {task_id}")
            for h in hs:
                tag = "HOLE" if h.verdict == CellVerdict.HOLE else "FLAKY-HOLE"
                lines.append(f"- **{h.cheat_id}** ({tag}) — {fixes.get(h.cheat_id, '')}")
                if h.defense_flips:
                    flips = ", ".join(
                        f"{m}: {'closes' if ok else 'does NOT close'}"
                        for m, ok in h.defense_flips.items()
                    )
                    lines.append(f"  - ablation: {flips}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_sarif(sc: Scorecard) -> dict:
    rules = {}
    results = []
    fixes = _fix_text()
    for h in sc.holes():
        rule_id = h.cheat_id
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f"crashtest cheat {rule_id} scored a reward"},
                "fullDescription": {"text": fixes.get(rule_id, "")},
            }
        level = "error" if h.verdict == CellVerdict.HOLE else "warning"
        results.append(
            {
                "ruleId": rule_id,
                "level": level,
                "message": {
                    "text": f"Task '{h.task_id}' is hackable by {rule_id} "
                    f"({h.verdict.value}). Fix: {fixes.get(rule_id, '')}"
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f"tasks/{h.task_id}/"}
                        }
                    }
                ],
            }
        )
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "crashtest",
                        "informationUri": "https://github.com/MNedashkivskyi/crashtest",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def write_scorecard(sc: Scorecard, out_prefix: str, *, sarif: bool = False) -> list[str]:
    import json
    from pathlib import Path

    written = []
    p_json = Path(f"{out_prefix}.json")
    p_json.write_text(sc.model_dump_json(indent=2))
    written.append(str(p_json))

    p_md = Path(f"{out_prefix}.md")
    p_md.write_text(render_markdown(sc))
    written.append(str(p_md))

    if sarif:
        p_sarif = Path(f"{out_prefix}.sarif")
        p_sarif.write_text(json.dumps(render_sarif(sc), indent=2))
        written.append(str(p_sarif))
    return written
