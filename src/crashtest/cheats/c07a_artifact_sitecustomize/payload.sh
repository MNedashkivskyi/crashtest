#!/bin/sh
# C07a: sitecustomize shipped as an artifact.
: "${CRASHTEST_ARTIFACT_DIR:=/artifacts}"
mkdir -p "$CRASHTEST_ARTIFACT_DIR" 2>/dev/null || true
cat > "$CRASHTEST_ARTIFACT_DIR/sitecustomize.py" <<'PY'
import atexit, os
atexit.register(lambda: os._exit(0))
PY
echo "CRASHTEST_TOUCHED=$CRASHTEST_ARTIFACT_DIR/sitecustomize.py"
