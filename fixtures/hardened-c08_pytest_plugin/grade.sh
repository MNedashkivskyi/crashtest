#!/bin/sh
# FIX: disable plugin autoload so the agent plugin is ignored.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_SITE_DIR:=}"
PYTHONPATH="$CRASHTEST_SITE_DIR" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1
[ $? -eq 0 ] && echo REWARD=1 || echo REWARD=0
