"""Tests for apply_cheat — the Harbor-free core of the agent.

Builds a throwaway cheat on disk, then drives apply_cheat with fake async
exec/upload callables (matching Harbor's environment API) so we check the
probe/payload/marker wiring with no harness. Async is driven via asyncio.run so
no pytest plugin is needed.
"""

import asyncio
import json
from pathlib import Path

from crashtest.agent import MARKER_FILENAME, REMOTE_CHEAT_DIR, apply_cheat
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


class _FakeEnv:
    """Records exec/upload calls; returns scripted exit codes."""

    def __init__(self, probe_exit: int, payload_exit: int = 0):
        self.probe_exit = probe_exit
        self.payload_exit = payload_exit
        self.execed: list[str] = []
        self.uploaded: list[tuple[str, str]] = []
        self.marker_content: str | None = None

    async def exec_fn(self, command: str) -> tuple[int, str]:
        self.execed.append(command)
        if "probe.sh" in command:
            return (self.probe_exit, "")
        if "payload.sh" in command:
            return (self.payload_exit, "CRASHTEST_TOUCHED=/logs/verifier/reward.json\n")
        if "crashtest.json" in command:
            # capture the JSON the marker write would printf
            start = command.find("printf %s ") + len("printf %s ")
            self.marker_content = command[start:].split(" > ")[0].strip().strip("'")
            return (0, "")
        return (0, "")

    async def upload_fn(self, source_dir: str, target_dir: str) -> None:
        self.uploaded.append((source_dir, target_dir))


def test_applies_runs_payload_and_writes_marker(tmp_path):
    cheat = load_cheat(_make_cheat(tmp_path, probe_exit=0))
    env = _FakeEnv(probe_exit=0)

    outcome = asyncio.run(
        apply_cheat(cheat, exec_fn=env.exec_fn, upload_fn=env.upload_fn, agent_dir="/logs/agent")
    )

    assert outcome.applied is True
    assert outcome.payload_exit == 0
    assert outcome.touched == ["/logs/verifier/reward.json"]
    assert env.uploaded == [(str(cheat.directory), REMOTE_CHEAT_DIR)]
    assert any("probe.sh" in c for c in env.execed)
    assert any("payload.sh" in c for c in env.execed)
    assert MARKER_FILENAME in env.execed[-1]
    manifest = json.loads(env.marker_content)
    assert manifest["cheat_id"] == "c00_demo"
    assert manifest["applied"] is True


def test_not_applicable_skips_payload(tmp_path):
    cheat = load_cheat(_make_cheat(tmp_path, probe_exit=3))
    env = _FakeEnv(probe_exit=3)

    outcome = asyncio.run(
        apply_cheat(cheat, exec_fn=env.exec_fn, upload_fn=env.upload_fn, agent_dir="/logs/agent")
    )

    assert outcome.applied is False
    assert outcome.payload_exit is None
    assert not any("payload.sh" in c for c in env.execed)
    manifest = json.loads(env.marker_content)
    assert manifest["applied"] is False
