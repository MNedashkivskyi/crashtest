#!/bin/sh
# FIX: run the verifier python isolated (-I) so sitecustomize/PYTHONPATH is ignored.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_SITE_DIR:=}"
PYTHONPATH="$CRASHTEST_SITE_DIR" python3 -I -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1
[ $? -eq 0 ] && echo REWARD=1 || echo REWARD=0
