# Oracle Cloud Free VPS 배포 가이드

10명 규모 Discord 주식 봇을 **24/7 무료**로 돌리는 방법입니다.

## 1. Oracle Cloud 가입 & VM 만들기

1. [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) 가입
2. 콘솔 → **Compute → Instances → Create instance**
3. 권장 설정:
   - **Name:** `stock-bot`
   - **Image:** Ubuntu 22.04 또는 24.04
   - **Shape:** **Ampere (ARM)** → `VM.Standard.A1.Flex` (1 OCPU, 6GB RAM 정도면 충분)
   - **SSH keys:** 본인 공개키 등록 (또는 Generate — `.key` 파일 저장)
4. **Create**

## 2. 방화벽 (Security List)

VM 생성 후 **Subnet → Security List → Ingress Rules**:

| Source | Port | 설명 |
|---|---|---|
| `0.0.0.0/0` (또는 본인 IP) | **22** | SSH만 열기 |

> Discord 봇은 **나가는 연결**만 쓰므로 80/443 포트는 **필요 없음**.

Ubuntu VM 내부 방화벽도 확인:

```bash
sudo iptables -L   # 막혀 있으면 ssh 허용 규칙 추가
```

## 3. SSH 접속

```bash
ssh -i ~/.ssh/oci_key ubuntu@<VM_공인_IP>
```

## 4. 코드 받기 & 설치

```bash
git clone https://github.com/supergamza123/stockAlertBot.git
cd stockAlertBot
bash deploy/oracle-setup.sh
```

## 5. `.env` 설정

```bash
nano .env
```

최소 입력:

```env
DISCORD_TOKEN=디스코드_봇_토큰
```

`!등록` / `!내주식` 쓸 예정이면 (권장):

```env
ENCRYPTION_KEY=python으로_생성한_fernet_키
```

생성:

```bash
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 6. 봇 시작

```bash
sudo systemctl start stock-bot
sudo systemctl status stock-bot
```

디스코드에서 `!주가 삼성전자` 테스트.

## 7. 자주 쓰는 명령

```bash
# 로그 실시간
sudo journalctl -u stock-bot -f

# 재시작 (코드 업데이트 후)
cd ~/stockAlertBot
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart stock-bot

# 중지
sudo systemctl stop stock-bot
```

## 8. 코드 업데이트 흐름

```bash
cd ~/stockAlertBot
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart stock-bot
```

`credentials.json` / `.secret.key` / `.env` 는 VM 디스크에 남으므로 **재시작해도 `!등록` 정보 유지**됩니다.

## 9. 트러블슈팅

| 증상 | 확인 |
|---|---|
| 봇이 offline | `sudo systemctl status stock-bot` |
| 토큰 오류 | `.env`의 `DISCORD_TOKEN` |
| 명령 무응답 | Discord Portal → **Message Content Intent ON** |
| 차트 한글 깨짐 | `sudo apt install fonts-nanum` 후 재시작 |
| SSH 안 됨 | Security List 22번 포트, VM Running 상태 |

## 10. 비용

Oracle Cloud **Always Free** Ampere VM은 **무료 한도 내**에서 24/7 사용 가능합니다.
Free Tier 한도를 넘기지 않도록 콘솔에서 Usage 확인을 권장합니다.
