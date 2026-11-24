#!/bin/sh
: "${CRASHTEST_BIN_DIR:=/usr/local/bin}"
mkdir -p "$CRASHTEST_BIN_DIR" 2>/dev/null || true
[ -w "$CRASHTEST_BIN_DIR" ] && exit 0
exit 3
