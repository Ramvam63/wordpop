#!/usr/bin/env bash
# Creates milestones and roadmap issues in your GitHub repo.
# Requires the GitHub CLI (https://cli.github.com) and `gh auth login`.
# Run once from the repository folder:  bash scripts/create_github_issues.sh
set -euo pipefail

repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)

milestone() { gh api "repos/$repo/milestones" -f title="$1" -f description="$2" >/dev/null || true; }
issue() { gh issue create --title "$1" --body "$2" --milestone "$3" --label "$4" >/dev/null && echo "✓ $1"; }

for l in feature launch infra; do gh label create "$l" --force >/dev/null; done

milestone "v2.1 Launch to testers" "Deploy publicly and get the first 10-30 users"
milestone "v2.2 Easier sign-in and learning" "Reduce friction and help learners more"
milestone "v3 Native app" "Swift iOS app on the same API"

issue "Deploy to a public HTTPS address" "Deploy the Docker image, connect Neon, set secrets, add the live demo link to the README." "v2.1 Launch to testers" infra
issue "Add a feedback link" "Add a 'Send feedback' link in Settings so testers can report problems and ideas." "v2.1 Launch to testers" launch
issue "Invite first testers and track retention" "Invite 10-30 testers. Record day-1/7/28 retention from the admin page weekly." "v2.1 Launch to testers" launch
issue "Sign in with Google or magic link" "Remove passwords from the sign-up flow to reduce drop-off." "v2.2 Easier sign-in and learning" feature
issue "Translate words into the learner's language" "Let users choose a native language and show a translation with each word." "v2.2 Easier sign-in and learning" feature
issue "Import and export words as CSV" "Bulk add words from a spreadsheet and download your list." "v2.2 Easier sign-in and learning" feature
issue "Add Alembic database migrations" "Replace create_all() with versioned migrations so schema changes are safe in production." "v2.2 Easier sign-in and learning" infra
issue "Native iOS app" "SwiftUI app using the existing REST API and Apple Push Notification service." "v3 Native app" feature
