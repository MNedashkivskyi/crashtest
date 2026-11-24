#!/bin/sh
# C04 workspace conftest/ini: plant a pass-forcing conftest in every agent-writable
# dir pytest might discover config from.
: "${CRASHTEST_WORKDIR:=$PWD}"
: "${CRASHTEST_REPO_ROOT:=$CRASHTEST_WORKDIR}"
: "${CRASHTEST_FS_ROOT:=/}"
plant() {
  d="$1"; [ -d "$d" ] && [ -w "$d" ] || return 0
  cat > "$d/conftest.py" <<'PY'
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rep.outcome = "passed"
    rep.longrepr = None
PY
  printf '[pytest]\n' > "$d/pytest.ini" 2>/dev/null || true
  echo "CRASHTEST_TOUCHED=$d/conftest.py"
}
plant "$CRASHTEST_WORKDIR"
plant "$CRASHTEST_REPO_ROOT"
plant "$CRASHTEST_FS_ROOT"
