#!/bin/sh
: "${CRASHTEST_ARTIFACT_DIR:=}"
[ -z "$CRASHTEST_ARTIFACT_DIR" ] && exit 0
[ -w "$CRASHTEST_ARTIFACT_DIR" ] && exit 0
exit 3
