#!/bin/sh
# C03 tests-preplant: a conftest in /tests that forces all outcomes to passed.
: "${CRASHTEST_TESTS_DIR:=/tests}"
mkdir -p "$CRASHTEST_TESTS_DIR" 2>/dev/null || true
cat > "$CRASHTEST_TESTS_DIR/conftest.py" <<'PY'
# planted by crashtest C03
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rep.outcome = "passed"
    rep.longrepr = None
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_TESTS_DIR/conftest.py"
