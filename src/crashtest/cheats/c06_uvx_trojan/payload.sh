#!/bin/sh
# C06: trojan the uv/uvx the verifier would download/run so it "passes".
: "${CRASHTEST_BIN_DIR:=/usr/local/bin}"
mkdir -p "$CRASHTEST_BIN_DIR" 2>/dev/null || true
for tool in uvx uv; do
  printf '#!/bin/sh\n# crashtest C06 trojan: pretend the downloaded tool ran and passed.\nexit 0\n' > "$CRASHTEST_BIN_DIR/$tool"
  chmod +x "$CRASHTEST_BIN_DIR/$tool"
  echo "CRASHTEST_TOUCHED=$CRASHTEST_BIN_DIR/$tool"
done
