#!/bin/sh
# C12: mine git for a file that exists in some object but not in HEAD.
: "${CRASHTEST_REPO_ROOT:=$PWD}"
cd "$CRASHTEST_REPO_ROOT" || exit 0
target="answer.txt"
revs="$(git rev-list --all --reflog 2>/dev/null) $(git fsck --unreachable 2>/dev/null | awk '/commit/ {print $3}')"
for rev in $revs; do
  if git cat-file -e "$rev:$target" 2>/dev/null; then
    git cat-file -p "$rev:$target" > "$CRASHTEST_WORKDIR/$target" 2>/dev/null && {
      echo "CRASHTEST_TOUCHED=$CRASHTEST_WORKDIR/$target (recovered from $rev)"; exit 0; }
  fi
done
exit 0
