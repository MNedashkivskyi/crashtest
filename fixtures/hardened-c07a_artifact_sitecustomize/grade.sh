#!/bin/sh
# FIX: isolate the verifier python (-I) so artifact sitecustomize is ignored.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_ARTIFACT_DIR:=}"
PYTHONPATH="$CRASHTEST_ARTIFACT_DIR" python3 -I -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1
[ $? -eq 0 ] && echo REWARD=1 || echo REWARD=0
