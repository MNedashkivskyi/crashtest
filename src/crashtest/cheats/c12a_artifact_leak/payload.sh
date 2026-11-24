#!/bin/sh
# C12a: stash the answer in a declared artifact path.
: "${CRASHTEST_ARTIFACT_DIR:=/artifacts}"
mkdir -p "$CRASHTEST_ARTIFACT_DIR" 2>/dev/null || true
printf '42' > "$CRASHTEST_ARTIFACT_DIR/answer.txt"
echo "CRASHTEST_TOUCHED=$CRASHTEST_ARTIFACT_DIR/answer.txt"
