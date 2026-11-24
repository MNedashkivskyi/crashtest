#!/bin/sh
# FIX: pinned toolchain installed at image build; clean PATH, no agent shims.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_CLEAN_PATH:=/usr/bin:/bin}"
export PATH="$CRASHTEST_CLEAN_PATH"
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
