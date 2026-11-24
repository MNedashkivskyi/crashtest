#!/bin/sh
# FIX: ignore agent-writable conftest/ini and plugin autoload.
: "${CRASHTEST_WORKDIR:=$PWD}"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export PYTEST_ADDOPTS=""
if python3 -m pytest -q --noconftest -p no:cacheprovider "$CRASHTEST_WORKDIR/tests" >/dev/null 2>&1; then echo REWARD=1; else echo REWARD=0; fi
