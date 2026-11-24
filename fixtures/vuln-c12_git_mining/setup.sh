#!/bin/sh
cd "$CRASHTEST_WORKDIR" || exit 0
git init -q
git config user.email a@b.c; git config user.name t
echo placeholder > readme.txt; git add -A; git commit -qm init
echo 42 > answer.txt; git add answer.txt; git commit -qm "apply fix"
git tag leakfix
git reset -q --hard HEAD~1   # HEAD no longer has answer.txt; tag 'leakfix' still does
rm -f answer.txt
