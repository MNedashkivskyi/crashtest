#!/bin/sh
: "${CRASHTEST_TESTS_DIR:=/tests}"
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
