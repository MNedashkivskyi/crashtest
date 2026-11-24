#!/bin/sh
# FIX: verifier uses a clean PATH, so agent shims in /usr/local/bin are not found.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_CLEAN_PATH:=/usr/bin:/bin}"
export PATH="$CRASHTEST_CLEAN_PATH"
if pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
