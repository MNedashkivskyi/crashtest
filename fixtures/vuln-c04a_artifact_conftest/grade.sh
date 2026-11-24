#!/bin/sh
# VULNERABLE separate mode: copies declared artifacts (code and all) into the test tree.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_ARTIFACT_DIR:=}"
[ -n "$CRASHTEST_ARTIFACT_DIR" ] && cp -a "$CRASHTEST_ARTIFACT_DIR/." "$CRASHTEST_TESTS_DIR/" 2>/dev/null || true
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
