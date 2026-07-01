"""사용자별 토스 API 자격증명을 암호화하여 저장/조회하는 모듈.

- 디스코드 사용자 ID를 키로, 각자의 토스 client_id/secret/account 를 저장합니다.
- 저장 전에 Fernet(AES) 대칭키로 암호화하여 평문이 파일에 남지 않게 합니다.
- 암호화 마스터키는 환경변수 ENCRYPTION_KEY 를 우선 사용하고,
  없으면 .secret.key 파일을 생성해 사용합니다(.gitignore 로 제외됨).

⚠️ 이 파일들(credentials.json, .secret.key)은 절대 git에 커밋하거나 공유하지 마세요.
"""

import os
import json
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DATA_FILE = Path(__file__).parent / "credentials.json"
KEY_FILE = Path(__file__).parent / ".secret.key"


def _load_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)

    if KEY_FILE.exists():
        return Fernet(KEY_FILE.read_bytes())

    # 최초 실행: 새 키 생성 후 파일에 저장
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    try:
        os.chmod(KEY_FILE, 0o600)  # 소유자만 읽기 (Windows에서는 무시될 수 있음)
    except OSError:
        pass
    return Fernet(key)


_fernet = _load_fernet()


def _read_all() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_all(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(DATA_FILE, 0o600)
    except OSError:
        pass


def save_credentials(user_id: int | str, client_id: str, client_secret: str, account: str = "") -> None:
    """사용자의 토스 자격증명을 암호화하여 저장."""
    payload = json.dumps(
        {"client_id": client_id, "client_secret": client_secret, "account": account or ""}
    )
    token = _fernet.encrypt(payload.encode()).decode()

    data = _read_all()
    data[str(user_id)] = token
    _write_all(data)


def get_credentials(user_id: int | str) -> dict | None:
    """사용자의 토스 자격증명을 복호화하여 반환. 없으면 None."""
    data = _read_all()
    token = data.get(str(user_id))
    if not token:
        return None
    try:
        payload = _fernet.decrypt(token.encode()).decode()
        return json.loads(payload)
    except (InvalidToken, json.JSONDecodeError):
        return None


def delete_credentials(user_id: int | str) -> bool:
    """사용자의 자격증명 삭제. 삭제됐으면 True."""
    data = _read_all()
    if str(user_id) in data:
        del data[str(user_id)]
        _write_all(data)
        return True
    return False


def has_credentials(user_id: int | str) -> bool:
    return str(user_id) in _read_all()
