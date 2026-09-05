#!/usr/bin/env bash
# Sync local wiki/ directory to the GitHub repository wiki
set -euo pipefail

REPO="youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor"
TMP_DIR="/tmp/autotune-wiki-sync"

echo "Syncing wiki pages to ${REPO}.wiki.git..."

rm -rf "${TMP_DIR}"
TOKEN=$(gh auth token)
git clone "https://x-access-token:${TOKEN}@github.com/${REPO}.wiki.git" "${TMP_DIR}"

cp -r wiki/* "${TMP_DIR}/"
cd "${TMP_DIR}"

git add .
if git diff --cached --quiet; then
  echo "Wiki is already up to date."
else
  git commit -m "docs(wiki): update documentation pages"
  git push origin master
  echo "Wiki pages synchronized successfully."
fi

rm -rf "${TMP_DIR}"
