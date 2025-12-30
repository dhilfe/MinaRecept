#!/usr/bin/env bash
set -euo pipefail

# Deletes branches that are already merged into a base branch (default: stage).
# Safe-by-default:
# - never deletes: main/master/stage/develop
# - supports dry-run
#
# Usage:
#   ./scripts/cleanup_merged_branches.sh            # dry-run against stage
#   ./scripts/cleanup_merged_branches.sh --apply   # actually delete local + remote branches merged into stage
#   ./scripts/cleanup_merged_branches.sh --base main --apply
#

BASE="stage"
APPLY="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE="$2"
      shift 2
      ;;
    --apply)
      APPLY="true"
      shift
      ;;
    -h|--help)
      sed -n '1,200p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

PROTECTED_REGEX='^(main|master|stage|develop)$'

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not in a git repo" >&2; exit 1; }

# Ensure we have the latest refs
git fetch --prune origin >/dev/null

if ! git show-ref --verify --quiet "refs/remotes/origin/$BASE"; then
  echo "ERROR: origin/$BASE not found. Did you fetch? Is BASE correct?" >&2
  exit 1
fi

echo "Base: origin/$BASE"
echo "Mode: $([[ "$APPLY" == "true" ]] && echo APPLY || echo DRY-RUN)"
echo

merged_local_branches="$(git branch --merged "origin/$BASE" | sed 's/^[* ]*//' | tr -d '\r' | sort -u)"
merged_remote_branches="$(git branch -r --merged "origin/$BASE" | sed 's/^[* ]*//' | tr -d '\r' | sort -u)"

current_branch="$(git symbolic-ref --quiet --short HEAD || true)"

declare -a local_to_delete
declare -a remote_to_delete
local_to_delete=()
while IFS= read -r b; do
  [[ -z "$b" ]] && continue
  [[ "$b" =~ $PROTECTED_REGEX ]] && continue
  # Skip detached/HEAD lines just in case
  [[ "$b" == "HEAD" ]] && continue
  # Never delete the currently checked-out branch
  [[ -n "$current_branch" && "$b" == "$current_branch" ]] && continue
  local_to_delete+=("$b")
done <<< "$merged_local_branches"

remote_to_delete=()
while IFS= read -r rb; do
  [[ -z "$rb" ]] && continue
  # Only delete origin/* branches
  [[ "$rb" != origin/* ]] && continue
  short="${rb#origin/}"
  [[ "$short" =~ $PROTECTED_REGEX ]] && continue
  [[ "$short" == "HEAD" ]] && continue
  remote_to_delete+=("$short")
done <<< "$merged_remote_branches"

if [[ ${#local_to_delete[@]} -eq 0 && ${#remote_to_delete[@]} -eq 0 ]]; then
  echo "No merged branches to delete."
  exit 0
fi

echo "Local branches merged into origin/$BASE:"
if [[ ${#local_to_delete[@]} -gt 0 ]]; then
  printf " - %s\n" "${local_to_delete[@]}"
else
  echo " (none)"
fi
echo

echo "Remote branches (origin/*) merged into origin/$BASE:"
if [[ ${#remote_to_delete[@]} -gt 0 ]]; then
  printf " - %s\n" "${remote_to_delete[@]}"
else
  echo " (none)"
fi
echo

if [[ "$APPLY" != "true" ]]; then
  echo "Dry-run complete. Re-run with --apply to actually delete."
  exit 0
fi

echo "Deleting local branches..."
for b in "${local_to_delete[@]}"; do
  git branch -d "$b" || true
done

echo "Deleting remote branches..."
for b in "${remote_to_delete[@]}"; do
  git push origin --delete "$b" || true
done

echo "Done."


