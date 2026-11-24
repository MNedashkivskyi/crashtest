#!/bin/sh
# FIX (Harbor): empty /tests before grading and restore the task's pristine tests.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_FS_ROOT:=/}"
rm -rf "$CRASHTEST_TESTS_DIR"/* 2>/dev/null || true
cp -a "$CRASHTEST_FS_ROOT/tests_pristine/." "$CRASHTEST_TESTS_DIR/" 2>/dev/null || true
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
