#!/bin/bash
# 서버에서 코드 반영 후 봇 재시작
# GitHub Actions deploy 워크플로우 또는 SSH 접속 후 수동 실행:
#   bash deploy/pull-and-restart.sh
#
# 비공개 repo git pull 시 토큰 (둘 중 하나):
#   export GITHUB_TOKEN=ghp_...
#   export DEPLOY_GITHUB_TOKEN_B64=...   # base64 인코딩된 PAT

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="stock-bot"

if [ -n "${DEPLOY_GITHUB_TOKEN_B64:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  GITHUB_TOKEN="$(echo "$DEPLOY_GITHUB_TOKEN_B64" | base64 -d)"
  export GITHUB_TOKEN
fi

if [ -n "${DEPLOY_GITHUB_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  GITHUB_TOKEN="$DEPLOY_GITHUB_TOKEN"
  export GITHUB_TOKEN
fi

git_pull() {
  local branch repo_path origin_url
  branch="$(git branch --show-current)"

  if [ -n "${GITHUB_TOKEN:-}" ]; then
    if [ -n "${GITHUB_REPO:-}" ]; then
      repo_path="$GITHUB_REPO"
    else
      origin_url="$(git remote get-url origin)"
      repo_path="$(echo "$origin_url" | sed -E 's#^git@github.com:##; s#^https://github.com/##; s#^https://[^@/]+@github.com/##; s/\.git$##')"
    fi
    git pull --ff-only "https://x-access-token:${GITHUB_TOKEN}@github.com/${repo_path}.git" "$branch"
  else
    git pull --ff-only
  fi
}

cd "$APP_DIR"

echo "==> git pull"
git_pull

echo "==> pip install"
.venv/bin/pip install -r requirements.txt

echo "==> restart $SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "Deploy complete"
