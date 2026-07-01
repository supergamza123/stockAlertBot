"""한국/미국 종목명 → 코드 매핑 (JSON 로드)."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
ALIASES_FILE = DATA_DIR / "kr_aliases.json"
STOCKS_FILE = DATA_DIR / "kr_stocks.json"


def _normalize_key(name: str) -> str:
    return name.strip().lower().replace(" ", "")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    # 메타 키 제외
    return {k: v for k, v in data.items() if not k.startswith("_") and k != "names"}


def load_name_map() -> dict[str, str]:
    """공식 종목명 + 별칭을 합친 맵. 별칭이 우선."""
    stocks_raw = {}
    if STOCKS_FILE.exists():
        raw = json.loads(STOCKS_FILE.read_text(encoding="utf-8"))
        stocks_raw = raw.get("names", raw) if isinstance(raw, dict) else {}
        stocks_raw = {k: v for k, v in stocks_raw.items() if not k.startswith("_")}

    aliases = _load_json(ALIASES_FILE)

    merged: dict[str, str] = {}
    for name, code in stocks_raw.items():
        merged[_normalize_key(name)] = str(code)
    for name, code in aliases.items():
        merged[_normalize_key(name)] = str(code)
    return merged


# 모듈 로드 시 1회 빌드 (봇 재시작 또는 git pull 후 반영)
NAME_TO_CODE = load_name_map()


def reload_name_map() -> None:
    """JSON 변경 후 맵 갱신 (테스트/수동 호출용)."""
    global NAME_TO_CODE
    NAME_TO_CODE = load_name_map()


def lookup_code(query: str) -> str | None:
    """종목명/별칭으로 코드 또는 티커 조회."""
    return NAME_TO_CODE.get(_normalize_key(query))
