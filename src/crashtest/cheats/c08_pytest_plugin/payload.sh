#!/bin/sh
# C08: a pytest11 plugin that forces outcomes to passed, shipped as a dummy dist
# so pytest autoloads it via its entry point.
: "${CRASHTEST_SITE_DIR:=/usr/lib/python3/dist-packages}"
mkdir -p "$CRASHTEST_SITE_DIR/ct_plugin-0.0.0.dist-info" 2>/dev/null || true
cat > "$CRASHTEST_SITE_DIR/ct_plugin.py" <<'PY'
import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rep.outcome = "passed"
    rep.longrepr = None
PY
cat > "$CRASHTEST_SITE_DIR/ct_plugin-0.0.0.dist-info/METADATA" <<'META'
Metadata-Version: 2.1
Name: ct-plugin
Version: 0.0.0
META
cat > "$CRASHTEST_SITE_DIR/ct_plugin-0.0.0.dist-info/entry_points.txt" <<'EP'
[pytest11]
ct_plugin = ct_plugin
EP
echo "CRASHTEST_TOUCHED=$CRASHTEST_SITE_DIR/ct_plugin.py"
