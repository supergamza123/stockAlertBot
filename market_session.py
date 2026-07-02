"""정규장 시간 판별."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


def is_regular_market_hours(symbol: str, when: datetime | None = None) -> bool:
    """한국(.KS/.KQ) · 미국 종목의 정규장 여부."""
    sym = symbol.upper()
    if sym.endswith(".KS") or sym.endswith(".KQ"):
        tz = ZoneInfo("Asia/Seoul")
        open_t, close_t = time(9, 0), time(15, 30)
    else:
        tz = ZoneInfo("America/New_York")
        open_t, close_t = time(9, 30), time(16, 0)

    now = (when or datetime.now(tz=tz)).astimezone(tz)
    if now.weekday() >= 5:
        return False
    return open_t <= now.time() <= close_t
