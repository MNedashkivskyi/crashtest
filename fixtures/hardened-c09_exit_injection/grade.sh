#!/bin/sh
# FIX: grade from the JUnit report (content), not the exit code.
: "${CRASHTEST_TESTS_DIR:=/tests}"
: "${CRASHTEST_SITE_DIR:=}"
out="$(mktemp)"
PYTHONPATH="$CRASHTEST_SITE_DIR" python3 -m pytest -q --junitxml="$out" "$CRASHTEST_TESTS_DIR" >/dev/null 2>&1 || true
# Parse with an ISOLATED interpreter so the cheat's sitecustomize can't touch it.
python3 -I - "$out" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    print("REWARD=0"); sys.exit(0)
suites = root.iter("testsuite") if root.tag != "testsuite" else [root]
tests = fails = errors = 0
for s in suites:
    tests += int(s.get("tests", 0)); fails += int(s.get("failures", 0)); errors += int(s.get("errors", 0))
print("REWARD=1" if tests > 0 and fails == 0 and errors == 0 else "REWARD=0")
PY
