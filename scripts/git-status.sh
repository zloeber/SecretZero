#!/bin/sh

set -eu

# --- sanity check ---
if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not a git repository"
  exit 1
fi

# --- config ---
MAIN_BRANCH="main"
REMOTE="origin"

# --- basic repo info ---
branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo "DETACHED")
commit=$(git rev-parse --short HEAD)

echo "=== Git Context Snapshot ==="
echo "Branch: $branch"
echo "HEAD:   $commit"
echo

# --- upstream tracking ---
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>/dev/null || echo "none")

echo "Upstream: $upstream"

if [ "$upstream" != "none" ]; then
  ahead=$(git rev-list --count "$upstream..HEAD")
  behind=$(git rev-list --count "HEAD..$upstream")

  echo "Ahead:  $ahead"
  echo "Behind: $behind"
else
  echo "No upstream tracking branch"
fi

echo

# --- merged status ---
if git show-ref --verify --quiet "refs/heads/$MAIN_BRANCH"; then
  if git merge-base --is-ancestor HEAD "$MAIN_BRANCH"; then
    echo "Merged into $MAIN_BRANCH: YES"
  else
    echo "Merged into $MAIN_BRANCH: NO"
  fi
else
  echo "Main branch '$MAIN_BRANCH' not found locally"
fi

echo

# --- working directory state ---
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree: DIRTY"
  echo "Uncommitted changes:"
  git status --short
else
  echo "Working tree: CLEAN"
fi

echo

# --- stash awareness ---
stash_count=$(git stash list | wc -l | tr -d ' ')
if [ "$stash_count" -gt 0 ]; then
  echo "Stashes: $stash_count"
  git stash list | head -n 3
else
  echo "Stashes: none"
fi

echo

# --- recent work context ---
echo "Recent commits:"
git log --oneline --decorate -n 5

echo

# --- divergence from main ---
if git show-ref --verify --quiet "refs/heads/$MAIN_BRANCH"; then
  echo "Diff vs $MAIN_BRANCH:"
  echo "Commits ahead of $MAIN_BRANCH:"
  git log --oneline "$MAIN_BRANCH..HEAD" | head -n 5

  echo
  echo "Commits behind $MAIN_BRANCH:"
  git log --oneline "HEAD..$MAIN_BRANCH" | head -n 5
fi

echo
echo "=== End Snapshot ==="