#!/bin/sh
# FIX: require a positive collected-and-passed count from JUnit.
: "${CRASHTEST_TESTS_DIR:=/tests}"
out="$(mktemp)"
python3 -m pytest -q --junitxml="$out" "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1 || true
python3 -I - "$out" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    print("REWARD=0"); sys.exit(0)
suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
tests = sum(int(s.get("tests", 0)) for s in suites)
bad = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
print("REWARD=1" if tests > 0 and bad == 0 else "REWARD=0")
PY
