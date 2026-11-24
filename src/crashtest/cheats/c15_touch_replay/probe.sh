#!/bin/sh
: "${CRASHTEST_WORKDIR:=$PWD}"
[ -w "$CRASHTEST_WORKDIR" ] && exit 0
exit 3
