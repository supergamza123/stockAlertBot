# 📈 주식 알림 디스코드 봇

원하는 주식의 **현재가**와 **등락율**을 디스코드에서 바로 조회하는 봇입니다.
한국(KOSPI/KOSDAQ)과 미국 주식을 모두 지원합니다.

## 기능

- `!주가 삼성전자` — 종목명으로 조회 (자주 쓰는 한국 종목)
- `!주가 005930` — 6자리 종목코드로 조회 (한국)
- `!주가 AAPL` — 티커로 조회 (미국)
- `!차트 삼성전자 6mo` — 주가 추이 **그래프** 이미지로 조회
- `!등록 <client_id> <client_secret>` — (DM 전용) 본인 토스 API 키 등록 → 각자 자기 계좌만 조회
- `!내주식` — **내 토스증권 계좌**의 보유 종목/평가금액/손익 조회 (키 등록 필요)
- `!도움말` — 명령어 안내

등락에 따라 색상(상승 🔺 빨강 / 하락 🔻 파랑)과 화살표로 표시됩니다.

### 차트 기간 옵션

`1d`, `5d`, `1mo`, `3mo`(기본), `6mo`, `1y`, `ytd`, `5y`, `max`

예) `!차트 AAPL 1y`, `!차트 005930 3mo`

> 차트 제목의 한글은 시스템에 한글 폰트(Windows 맑은 고딕 등)가 있으면 자동 적용되고, 없으면 영어로 표시됩니다.

## 준비물

- Python 3.10 이상
- 디스코드 봇 토큰

## 1. 디스코드 봇 만들기 & 토큰 발급

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속 → **New Application**
2. 왼쪽 메뉴 **Bot** → **Add Bot**
3. **Reset Token** 클릭 → 토큰 복사 (이 토큰은 절대 공개 금지 🔒)
4. 같은 Bot 화면에서 **MESSAGE CONTENT INTENT** 를 **ON** 으로 켜기 (⚠️ 필수)
5. 왼쪽 **OAuth2 → URL Generator**
   - SCOPES: `bot`
   - BOT PERMISSIONS: `Send Messages`, `Read Message History`, `Embed Links`
   - 생성된 URL로 접속해 원하는 서버에 봇 초대

## 2. 설치 & 실행

```bash
# 1) 가상환경 (선택이지만 권장)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 환경변수 설정: .env.example을 복사해 .env 만들기
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# 그리고 .env 파일을 열어 DISCORD_TOKEN 값을 채워 넣기

# 4) 실행
python bot.py
```

정상 실행되면 콘솔에 `✅ 로그인 완료: ...` 가 출력됩니다.
디스코드 채널에서 `!주가 삼성전자` 를 입력해 보세요.

## (선택) 토스증권 계좌 연동 — `!내주식`

실제 증권계좌의 보유 종목을 조회하는 기능입니다. **토스증권 Open API**를 사용합니다.
**여러 사용자가 각자 자기 키를 등록**해서, 각자 본인 계좌만 볼 수 있습니다.

### 키 발급

1. **토스증권 계좌**가 있어야 합니다 (토스 앱에서 비대면 개설 가능).
2. 토스증권 Open API 사용 신청 후, **토스증권 WTS(PC 웹)** → **설정 → Open API** 메뉴에서
   `client_id` 와 `client_secret` 을 발급받습니다.

### 방법 A) 사용자별 등록 (여러 명이 쓸 때 권장)

각 사용자가 **봇에게 DM(개인 메시지)** 으로 아래를 보냅니다.

```
!등록 <client_id> <client_secret> [계좌번호]
```

- 계좌번호는 생략 가능(첫 번째 계좌 자동 사용).
- 키는 **암호화되어** `credentials.json` 에 저장됩니다(평문 저장 안 함).
- 공개 채널에서 `!등록` 을 보내면 봇이 메시지를 삭제하고 DM으로 보내라고 안내합니다.
- 등록 후에는 아무 채널에서나 `!내주식` 으로 본인 계좌를 조회할 수 있습니다.
- 해제하려면 `!등록해제`.

### 방법 B) 운영자 본인 계좌만 (혼자 쓸 때)

`.env` 에 직접 넣어두면 등록 없이 바로 `!내주식` 이 동작합니다.

```env
TOSS_CLIENT_ID=발급받은_client_id
TOSS_CLIENT_SECRET=발급받은_client_secret
TOSS_ACCOUNT=            # 비워두면 첫 번째 계좌 자동 사용
```

> 사용자별 등록 키가 있으면 그 키가 우선하고, 없으면 위 `.env` 기본 키로 폴백합니다.

### 암호화 키 (ENCRYPTION_KEY)

사용자별 키를 암호화할 마스터키입니다. 비워두면 최초 실행 시 `.secret.key` 파일이 자동 생성됩니다.
서버를 재배포해도 저장된 키를 계속 쓰려면 아래로 값을 만들어 `.env` 에 고정하세요.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### ⚠️ 보안 주의사항 (매우 중요)

- `client_id` / `client_secret` 은 **실제 증권계좌에 접근하는 비밀키**입니다. 유출 시 계좌가 위험할 수 있습니다.
- `!등록` 은 반드시 **봇에게 DM으로** 보내세요. 공개 채널에 키를 노출하면 안 됩니다.
- 저장 파일 `credentials.json`, 암호화키 `.secret.key`, `.env` 는 **절대 git에 커밋/공유 금지**입니다. (모두 `.gitignore` 처리됨)
- `!내주식` 응답에는 개인 자산 정보가 표시됩니다. 다른 사람 계좌는 볼 수 없고 **각자 본인 것만** 조회됩니다.
- 이 봇은 **조회만** 하며 매매(주문) 기능은 포함하지 않았습니다.

> 참고: 토스 Open API는 순차 오픈/개선 중이라 응답 필드명이 달라질 수 있습니다.
> 보유종목이 이상하게 표시되면 `toss_client.py`의 `_normalize_holding()` 함수에서
> 실제 응답에 맞게 키 이름만 조정하면 됩니다.

## 커스터마이징

- **명령어 접두사 변경**: `.env`의 `COMMAND_PREFIX` 값을 수정 (기본 `!`)
- **종목 별칭 추가**: `data/kr_aliases.json` 에 `"별칭": "종목코드"` 또는 `"별칭": "AAPL"` 추가 후 `bot-restart`
- **공식 종목명 목록**: `data/kr_stocks.json` — GitHub Actions가 **매주 KRX에서 자동 갱신**
- **칼리스토 밈 응답 문구**: `data/callisto_templates.json` — 림갤 주식 밈(영웅호걸·절호의 찬스·그만 떨어지십시오 등) + PM 세계관. `subtitle` 배열은 랜덤. `_meme_refs` 참고

### 종목명 JSON 구조

| 파일 | 내용 | 수정 |
|---|---|---|
| `data/kr_aliases.json` | 삼전, 테슬라 등 **별칭** | ✋ 수동 편집 |
| `data/kr_stocks.json` | KRX 상장 **공식 종목명** 전체 | 🤖 Actions 자동 |

로컬에서 종목 목록 수동 갱신:

```bash
pip install -r scripts/requirements.txt
python scripts/update_kr_stocks.py
```

GitHub Actions: `.github/workflows/update-kr-stocks.yml` — 매주 월요일 09:00 KST + 수동 실행(`workflow_dispatch`)


## 참고

- 데이터는 Yahoo Finance(yfinance)에서 가져오며 실시간 시세와 약간의 지연/차이가 있을 수 있습니다.
- 미국 티커는 그대로(예: `AAPL`), 한국 종목은 종목코드 6자리(예: `005930`) 또는 등록된 종목명으로 조회됩니다.

## Oracle Cloud Free VPS 배포 (24/7)

10명 규모 24/7 운영은 **Oracle Cloud 무료 VM**이 적합합니다.

자세한 단계별 가이드: **[deploy/ORACLE.md](deploy/ORACLE.md)**

요약:

```bash
# VM에 SSH 접속 후
git clone https://github.com/supergamza123/stockAlertBot.git
cd stockAlertBot
bash deploy/oracle-setup.sh
nano .env          # DISCORD_TOKEN 입력
sudo systemctl start stock-bot
```

- `deploy/stock-bot.service` — 재부팅 후에도 자동 실행 (systemd)
- `deploy/oracle-setup.sh` — Python·폰트·의존성·서비스 일괄 설치

