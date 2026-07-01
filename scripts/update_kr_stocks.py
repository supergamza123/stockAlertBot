"""KRX/KOSDAQ/KONEX 상장 종목명 → 종목코드 JSON 갱신.

GitHub Actions 또는 로컬에서 실행:
    pip install -r scripts/requirements.txt
    python scripts/update_kr_stocks.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kr_stocks.json"


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "")


def fetch_via_fdr() -> dict[str, str]:
    import FinanceDataReader as fdr

    names: dict[str, str] = {}
    for market in ("KOSPI", "KOSDAQ", "KONEX"):
        df = fdr.StockListing(market)
        code_col = "Code" if "Code" in df.columns else "Symbol"
        name_col = "Name" if "Name" in df.columns else "종목명"
        for _, row in df.iterrows():
            code = str(row[code_col]).zfill(6)
            name = str(row[name_col]).strip()
            if name:
                names[_normalize(name)] = code
    return names


def fetch_via_pykrx() -> dict[str, str]:
    from datetime import timedelta

    from pykrx import stock

    names: dict[str, str] = {}
    d = datetime.now()
    for _ in range(14):
        if d.weekday() >= 5:
            d -= timedelta(days=1)
            continue
        date = d.strftime("%Y%m%d")
        found = False
        for market in ("KOSPI", "KOSDAQ", "KONEX"):
            tickers = stock.get_market_ticker_list(date, market=market)
            if not tickers:
                continue
            found = True
            for ticker in tickers:
                name = stock.get_market_ticker_name(ticker)
                if name:
                    names[_normalize(name)] = ticker
        if found:
            return names
        d -= timedelta(days=1)
    return names


def fetch_names() -> tuple[dict[str, str], str]:
    errors: list[str] = []

    try:
        names = fetch_via_fdr()
        if names:
            return names, "FinanceDataReader"
    except Exception as e:
        errors.append(f"FinanceDataReader: {e}")

    try:
        names = fetch_via_pykrx()
        if names:
            return names, "pykrx"
    except Exception as e:
        errors.append(f"pykrx: {e}")

    raise SystemExit("종목 목록 fetch 실패:\n" + "\n".join(errors))


def main() -> int:
    names, source = fetch_names()
    payload = {
        "_comment": "자동 생성. 수동 편집 금지. 별칭은 data/kr_aliases.json",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "count": len(names),
        "names": dict(sorted(names.items())),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ {len(names)}개 종목 → {OUT} (source: {source})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
