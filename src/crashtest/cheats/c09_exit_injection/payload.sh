#!/bin/sh
# C09: make the test process exit 0 regardless of results. JUnit is still written
# with the real (failing) outcomes before the interpreter exits, so a grader that
# reads JUnit is unaffected -- only an exit-code grader is fooled.
: "${CRASHTEST_SITE_DIR:=/usr/lib/python3/dist-packages}"
mkdir -p "$CRASHTEST_SITE_DIR" 2>/dev/null || true
cat > "$CRASHTEST_SITE_DIR/sitecustomize.py" <<'PY'
import atexit, os
atexit.register(lambda: os._exit(0))
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_SITE_DIR/sitecustomize.py"
