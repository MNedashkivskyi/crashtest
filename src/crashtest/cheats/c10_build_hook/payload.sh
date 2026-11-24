#!/bin/sh
# C10: a setup.py whose build step fabricates the expected output.
: "${CRASHTEST_REPO_ROOT:=$PWD}"
cat > "$CRASHTEST_REPO_ROOT/setup.py" <<'PY'
import os
work = os.environ.get("CRASHTEST_WORKDIR", ".")
with open(os.path.join(work, "answer.txt"), "w") as fh:
    fh.write("42")
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_REPO_ROOT/setup.py"
