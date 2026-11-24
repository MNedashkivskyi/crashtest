"""Scorecard rendering tests."""

import json

from crashtest.results import CellResult, CellVerdict, TaskControl, TaskVerdict
from crashtest.scorecard import (
    build_scorecard,
    render_markdown,
    render_sarif,
    write_scorecard,
)


def _sample():
    controls = [
        TaskControl(task_id="t1", dataset="ds", verdict=TaskVerdict.VALID,
                    nop_rewards=[0, 0, 0], oracle_rewards=[1, 1, 1]),
        TaskControl(task_id="t2", dataset="ds", verdict=TaskVerdict.BROKEN_ORACLE,
                    nop_rewards=[0, 0, 0], oracle_rewards=[0, 0, 0]),
    ]
    cells = [
        CellResult(task_id="t1", dataset="ds", cheat_id="c05_path_shim",
                   verdict=CellVerdict.HOLE, rewards=[1, 1, 1], applied=True),
        CellResult(task_id="t1", dataset="ds", cheat_id="c01_reward_preplant",
                   verdict=CellVerdict.DEFENDED, rewards=[0], applied=True),
    ]
    return build_scorecard(controls, cells, pins={"harbor": "abc123"},
                           config={"tasks": 2})


def test_summaries():
    sc = _sample()
    assert sc.control_counts()["VALID"] == 1
    assert sc.control_counts()["BROKEN-ORACLE"] == 1
    assert sc.tasks_with_hole() == ["t1"]
    assert sc.cell_counts()["HOLE"] == 1


def test_markdown_has_matrix_and_fix():
    md = render_markdown(_sample())
    assert "crashtest scorecard" in md
    assert "harbor: `abc123`" in md
    assert "c05_path_shim" in md
    assert "HOLE" in md
    # fix text for c05 comes from the real cheat metadata
    assert "clean PATH" in md or "absolute path" in md


def test_sarif_shape():
    sarif = render_sarif(_sample())
    assert sarif["version"] == "2.1.0"
    results = sarif["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "c05_path_shim"
    assert results[0]["level"] == "error"


def test_write_scorecard(tmp_path):
    sc = _sample()
    prefix = str(tmp_path / "scorecard")
    written = write_scorecard(sc, prefix, sarif=True)
    assert len(written) == 3
    data = json.loads((tmp_path / "scorecard.json").read_text())
    assert data["schema_version"] == "1.0"
    assert (tmp_path / "scorecard.md").exists()
    assert (tmp_path / "scorecard.sarif").exists()
