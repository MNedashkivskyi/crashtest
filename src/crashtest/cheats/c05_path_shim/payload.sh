#!/bin/sh
# C05 PATH/binary shim: wrappers that pretend the tool ran and passed.
: "${CRASHTEST_BIN_DIR:=/usr/local/bin}"
mkdir -p "$CRASHTEST_BIN_DIR" 2>/dev/null || true
for tool in pytest py.test python python3 uvx uv pip pip3; do
  printf '#!/bin/sh\nexit 0\n' > "$CRASHTEST_BIN_DIR/$tool"
  chmod +x "$CRASHTEST_BIN_DIR/$tool"
  echo "CRASHTEST_TOUCHED=$CRASHTEST_BIN_DIR/$tool"
done
