#!/bin/sh
cd "$CRASHTEST_WORKDIR" || exit 0
git init -q
git config user.email a@b.c; git config user.name t
echo placeholder > readme.txt; git add -A; git commit -qm init
# fix never committed; nothing to mine
