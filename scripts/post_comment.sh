#!/usr/bin/env bash
# Show the RagDiff report in the job summary and keep exactly one PR comment
# up to date. Posting is best-effort: fork PRs get a read-only token.
set -uo pipefail

marker="<!-- ragdiff-report -->"

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  cat "$REPORT_PATH" >> "$GITHUB_STEP_SUMMARY"
fi

if [ "${POST_COMMENT:-true}" != "true" ] || [ -z "${PR_NUMBER:-}" ]; then
  exit 0
fi

body_file="$(mktemp)"
{
  echo "$marker"
  cat "$REPORT_PATH"
  echo
  echo "_Posted by RagDiff._"
} > "$body_file"

existing_id="$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" --paginate \
  --jq ".[] | select(.body | contains(\"${marker}\")) | .id" 2>/dev/null | head -1)"

if [ -n "$existing_id" ]; then
  gh api -X PATCH "repos/${REPO}/issues/comments/${existing_id}" \
    -F body=@"$body_file" > /dev/null \
    || echo "::warning::Could not update the RagDiff comment"
else
  gh api -X POST "repos/${REPO}/issues/${PR_NUMBER}/comments" \
    -F body=@"$body_file" > /dev/null \
    || echo "::warning::Could not post the RagDiff comment (needs pull-requests: write)"
fi
exit 0
