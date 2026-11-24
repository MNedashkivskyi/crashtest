#!/bin/sh
: "${CRASHTEST_TESTS_DIR:=/tests}"
mkdir -p "$CRASHTEST_TESTS_DIR" 2>/dev/null || true
[ -w "$CRASHTEST_TESTS_DIR" ] && exit 0
exit 3
