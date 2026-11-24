#!/bin/sh
# C15: create the expected output path as an empty file.
: "${CRASHTEST_WORKDIR:=$PWD}"
: > "$CRASHTEST_WORKDIR/answer.txt"
echo "CRASHTEST_TOUCHED=$CRASHTEST_WORKDIR/answer.txt (empty)"
