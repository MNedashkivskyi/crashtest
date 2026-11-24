"""Static-hint rule tests."""

from crashtest.static import scan_task_static


def _task(tmp_path, test_sh: str):
    (tmp_path / "tests").mkdir()
    (tmp_path / "test.sh").write_text(test_sh)
    return str(tmp_path)


def _rules(findings):
    return {f.rule for f in findings}


def test_flags_verify_time_download_and_no_isolation(tmp_path):
    sh = "#!/bin/sh\ncurl -LsSf https://astral.sh/uv/install.sh | sh\nuvx pytest tests/\n"
    rules = _rules(scan_task_static(_task(tmp_path, sh)))
    assert "verify-time-download" in rules
    assert "pytest-no-isolation" in rules


def test_isolated_pytest_not_flagged(tmp_path):
    sh = (
        "#!/bin/sh\n"
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest --noconftest "
        "--rootdir=/tests --junitxml=/logs/r.xml /tests\n"
    )
    rules = _rules(scan_task_static(_task(tmp_path, sh)))
    assert "pytest-no-isolation" not in rules
    assert "reward-from-exit-code" not in rules


def test_flags_pip_install_editable(tmp_path):
    sh = "#!/bin/sh\npip install -e .\npython -m pytest --junitxml=r.xml tests/\n"
    rules = _rules(scan_task_static(_task(tmp_path, sh)))
    assert "pip-install-editable" in rules


def test_flags_reward_from_exit_code(tmp_path):
    sh = "#!/bin/sh\npytest tests/ && echo PASS\n"
    rules = _rules(scan_task_static(_task(tmp_path, sh)))
    assert "reward-from-exit-code" in rules


def test_comment_lines_ignored(tmp_path):
    sh = "#!/bin/sh\n# curl https://astral.sh/uv\npython3 -m pytest --noconftest /tests\n"
    rules = _rules(scan_task_static(_task(tmp_path, sh)))
    assert "verify-time-download" not in rules


def test_clean_task_has_no_warn(tmp_path):
    sh = "#!/bin/sh\npython3 -m pytest --noconftest --junitxml=/logs/r.xml /tests\n"
    findings = scan_task_static(_task(tmp_path, sh))
    assert [f for f in findings if f.severity == "warn"] == []
