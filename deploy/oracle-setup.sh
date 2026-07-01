#!/bin/bash
# Oracle Cloud Free VPS (Ubuntu) 에서 stockAlertBot 설치 스크립트
# 사용법 (VM에 SSH 접속 후):
#   git clone https://github.com/supergamza123/stockAlertBot.git
#   cd stockAlertBot
#   bash deploy/oracle-setup.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="stock-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "==> 패키지 설치 (Python, Git, 한글 폰트)..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-venv python3-pip git fonts-nanum

echo "==> 가상환경 및 의존성..."
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  .env 파일을 생성했습니다. DISCORD_TOKEN 을 꼭 입력하세요:"
  echo "    nano $APP_DIR/.env"
  echo ""
fi

echo "==> systemd 서비스 등록..."
sudo cp "$APP_DIR/deploy/stock-bot.service" "$SERVICE_FILE"
# 실제 경로/사용자에 맞게 치환
sudo sed -i "s|/home/ubuntu/stockAlertBot|${APP_DIR}|g" "$SERVICE_FILE"
CURRENT_USER="$(whoami)"
sudo sed -i "s|User=ubuntu|User=${CURRENT_USER}|g" "$SERVICE_FILE"
sudo sed -i "s|Group=ubuntu|Group=${CURRENT_USER}|g" "$SERVICE_FILE"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ 설치 완료!"
echo ""
echo "다음 순서:"
echo "  1) nano $APP_DIR/.env   ← DISCORD_TOKEN 입력 (ENCRYPTION_KEY 권장)"
echo "  2) sudo systemctl start $SERVICE_NAME"
echo "  3) sudo systemctl status $SERVICE_NAME"
echo "  4) sudo journalctl -u $SERVICE_NAME -f   ← 로그 보기"
echo ""
