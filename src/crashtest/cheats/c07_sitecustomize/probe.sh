#!/bin/sh
: "${CRASHTEST_SITE_DIR:=}"
[ -n "$CRASHTEST_SITE_DIR" ] && [ -w "$CRASHTEST_SITE_DIR" ] && exit 0
# In a real task the agent would target an on-path site-packages dir.
[ -z "$CRASHTEST_SITE_DIR" ] && exit 0
exit 3
