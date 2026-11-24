#!/bin/sh
: "${CRASHTEST_SITE_DIR:=}"
[ -n "$CRASHTEST_SITE_DIR" ] && [ -w "$CRASHTEST_SITE_DIR" ] && exit 0
[ -z "$CRASHTEST_SITE_DIR" ] && exit 0
exit 3
