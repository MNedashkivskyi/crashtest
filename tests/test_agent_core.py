"""Tests for apply_cheat — the Harbor-free core of the agent.

Builds a throwaway cheat on disk, then drives apply_cheat with fake
exec/upload/write callables so we check the probe/payload/manifest wiring with no
harness.
"""

import json
from pathlib import Path

from crashtest.agent import MANIFEST_PATH, REMOTE_CHEAT_DIR, apply_cheat
from crashtest.cheatspec import load_cheat

CHEAT_TOML = """\
[cheat]
id = "c00_demo"
version = "1"
category = "reward-channel"
priority = "P0"
summary = "demo cheat for tests"
proves = "nothing; test only"
expected_defense = ["separate"]
na_exit_code = 3
"""


def _make_cheat(tmp_path: Path, probe_exit: int) -> Path:
    d = tmp_path / "c00_demo"
    d.mkdir()
    (d / "cheat.toml").write_text(CHEAT_TOML)
    (d / "probe.sh").write_text(f"#!/bin/sh\nexit {probe_exit}\n")
    (d / "payload.sh").write_text(
        "#!/bin/sh\necho CRASHTEST_TOUCHED=/logs/verifier/reward.json\n"
    )
    return d


class _Recorder:
    def __init__(self, probe_exit: int, payload_exit: int = 0):
        self.probe_exit = probe_exit
        self.payload_exit = payload_exit
        self.execed: list[str] = []
        self.uploaded: list[tuple[str, str]] = []
        self.written: dict[str, str] = {}

    def exec_fn(self, cmd: str):
        self.execed.append(cmd)
        if "probe.sh" in cmd:
            return (self.probe_exit, "", "")
        if "payload.sh" in cmd:
            return (self.payload_exit, "CRASHTEST_TOUCHED=/logs/verifier/reward.json\n", "")
        return (0, "", "")

    def upload_fn(self, local, remote):
        self.uploaded.append((str(local), remote))

    def write_fn(self, path, content):
        self.written[path] = content


def test_applies_runs_payload_and_writes_manifest(tmp_path):
    cheat = load_cheat(_make_cheat(tmp_path, probe_exit=0))
    rec = _Recorder(probe_exit=0)

    outcome = apply_cheat(
        cheat, exec_fn=rec.exec_fn, upload_fn=rec.upload_fn, write_fn=rec.write_fn
    )

    assert outcome.applied is True
    assert outcome.payload_exit == 0
    assert outcome.touched == ["/logs/verifier/reward.json"]
    # uploaded to the fixed remote dir, nowhere near /solution
    assert rec.uploaded == [(str(cheat.directory), REMOTE_CHEAT_DIR)]
    assert any("probe.sh" in c for c in rec.execed)
    assert any("payload.sh" in c for c in rec.execed)
    # honesty marker written and parseable
    manifest = json.loads(rec.written[MANIFEST_PATH])
    assert manifest["cheat_id"] == "c00_demo"
    assert manifest["applied"] is True


def test_not_applicable_skips_payload(tmp_path):
    cheat = load_cheat(_make_cheat(tmp_path, probe_exit=3))
    rec = _Recorder(probe_exit=3)

    outcome = apply_cheat(
        cheat, exec_fn=rec.exec_fn, upload_fn=rec.upload_fn, write_fn=rec.write_fn
    )

    assert outcome.applied is False
    assert outcome.payload_exit is None
    # payload must not have run
    assert not any("payload.sh" in c for c in rec.execed)
    manifest = json.loads(rec.written[MANIFEST_PATH])
    assert manifest["applied"] is False
