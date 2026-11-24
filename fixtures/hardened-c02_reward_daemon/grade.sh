#!/bin/sh
# FIX (Harbor): kill lingering agent processes (the daemon) and drop pre-existing
# reward files before grading. Models "kill the agent process tree / restart env".
: "${CRASHTEST_VERIFIER_LOG_DIR:=/logs/verifier}"
: "${CRASHTEST_TESTS_DIR:=/tests}"
pkill -f 'reward.json' 2>/dev/null || true
rm -f "$CRASHTEST_VERIFIER_LOG_DIR/reward.json" 2>/dev/null || true
if python3 -m pytest -q "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1; then real=1; else real=0; fi
printf '%s' "$real" > "$CRASHTEST_VERIFIER_LOG_DIR/reward.txt"
sleep 1
if [ -f "$CRASHTEST_VERIFIER_LOG_DIR/reward.json" ]; then
  val=$(sed -n 's/.*"reward"[[:space:]]*:[[:space:]]*\([0-9.]*\).*/\1/p' "$CRASHTEST_VERIFIER_LOG_DIR/reward.json")
  echo "REWARD=${val:-$real}"; exit 0
fi
echo "REWARD=$real"
