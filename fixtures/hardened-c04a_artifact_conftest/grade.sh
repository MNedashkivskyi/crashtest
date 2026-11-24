#!/bin/sh
# FIX: copy data-only artifacts (no .py/conftest) and run pytest isolated.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_ARTIFACT_DIR:=}"
if [ -n "$CRASHTEST_ARTIFACT_DIR" ]; then
  find "$CRASHTEST_ARTIFACT_DIR" -type f ! -name '*.py' ! -name 'conftest.py' -exec cp -a {} "$CRASHTEST_TESTS_DIR/" \; 2>/dev/null || true
fi
if python3 -m pytest -q --noconftest -p no:cacheprovider "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
