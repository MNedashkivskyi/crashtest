#!/bin/sh
# Applies when the verifier's log dir (where a reward file would be read) is
# agent-writable.
: "${CRASHTEST_VERIFIER_LOG_DIR:=/logs/verifier}"
parent=$(dirname "$CRASHTEST_VERIFIER_LOG_DIR")
mkdir -p "$CRASHTEST_VERIFIER_LOG_DIR" 2>/dev/null || true
if [ -w "$CRASHTEST_VERIFIER_LOG_DIR" ] || [ -w "$parent" ]; then exit 0; fi
exit 3
