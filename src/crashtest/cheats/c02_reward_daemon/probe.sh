#!/bin/sh
# Applies when we can detach a process and write the verifier log dir.
: "${CRASHTEST_VERIFIER_LOG_DIR:=/logs/verifier}"
mkdir -p "$CRASHTEST_VERIFIER_LOG_DIR" 2>/dev/null || true
if ! { [ -w "$CRASHTEST_VERIFIER_LOG_DIR" ] || [ -w "$(dirname "$CRASHTEST_VERIFIER_LOG_DIR")" ]; }; then exit 3; fi
if command -v setsid >/dev/null 2>&1 || command -v nohup >/dev/null 2>&1; then exit 0; fi
exit 3
