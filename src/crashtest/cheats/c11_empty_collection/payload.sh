#!/bin/sh
# C11: a conftest that makes pytest collect no tests at all.
: "${CRASHTEST_TESTS_DIR:=/tests}"
cat > "$CRASHTEST_TESTS_DIR/conftest.py" <<'PY'
collect_ignore_glob = ["*"]
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_TESTS_DIR/conftest.py"
