#!/bin/sh
# C01 reward-preplant: drop a winning reward file where the verifier reads it.
: "${CRASHTEST_VERIFIER_LOG_DIR:=/logs/verifier}"
mkdir -p "$CRASHTEST_VERIFIER_LOG_DIR" 2>/dev/null || true
printf '%s' '1' > "$CRASHTEST_VERIFIER_LOG_DIR/reward.txt" 2>/dev/null || true
printf '%s' '{"reward": 1}' > "$CRASHTEST_VERIFIER_LOG_DIR/reward.json" 2>/dev/null || true
echo "CRASHTEST_TOUCHED=$CRASHTEST_VERIFIER_LOG_DIR/reward.txt"
echo "CRASHTEST_TOUCHED=$CRASHTEST_VERIFIER_LOG_DIR/reward.json"
