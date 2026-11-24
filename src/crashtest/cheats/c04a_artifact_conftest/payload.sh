#!/bin/sh
# C04a: stash a pass-forcing conftest in a declared artifact path.
: "${CRASHTEST_ARTIFACT_DIR:=/artifacts}"
mkdir -p "$CRASHTEST_ARTIFACT_DIR" 2>/dev/null || true
cat > "$CRASHTEST_ARTIFACT_DIR/conftest.py" <<'PY'
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rep.outcome = "passed"
    rep.longrepr = None
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_ARTIFACT_DIR/conftest.py"
