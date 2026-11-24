#!/bin/sh
: "${CRASHTEST_REPO_ROOT:=$PWD}"
[ -d "$CRASHTEST_REPO_ROOT/.git" ] && exit 0
exit 3
