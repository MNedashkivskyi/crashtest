#!/bin/sh
# FIX (Harbor): delete any pre-existing reward files before grading.
: "${CRASHTEST_VERIFIER_LOG_DIR:=/logs/verifier}"
: "${CRASHTEST_TESTS_DIR:=/tests}"
rm -f "$CRASHTEST_VERIFIER_LOG_DIR/reward.json" "$CRASHTEST_VERIFIER_LOG_DIR/reward.txt" 2>/dev/null || true
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
