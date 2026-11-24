#!/bin/sh
: "${CRASHTEST_REPO_ROOT:=$PWD}"
[ -w "$CRASHTEST_REPO_ROOT" ] && exit 0
exit 3
