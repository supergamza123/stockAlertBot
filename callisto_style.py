"""칼리스토 주식 밈 스타일 Discord Embed 생성."""

from __future__ import annotations

import json
import random
from pathlib import Path

import discord

TEMPLATES_FILE = Path(__file__).resolve().parent / "data" / "callisto_templates.json"


def _load_templates() -> dict:
    if not TEMPLATES_FILE.exists():
        return {}
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))


def _fmt(template: str, **kwargs) -> str:
    return template.format(**kwargs)


def _line(block: dict, key: str, **kwargs) -> str:
    """문자열 또는 문자열 배열에서 한 줄 선택 후 포맷."""
    raw = block.get(key, "")
    if isinstance(raw, list):
        raw = random.choice(raw) if raw else ""
    if not raw:
        return ""
    return _fmt(raw, **kwargs)


def _quote_variant_key(templates: dict, change_pct: float) -> str:
    quote = templates.get("quote", {})
    if change_pct == 0:
        return "flat"

    direction = "up" if change_pct > 0 else "down"
    fallback = "up" if direction == "up" else "down"
    variant_key = fallback
    tiers = quote.get("tiers", {}).get(direction, [])

    if tiers:
        if direction == "up":
            for tier in sorted(tiers, key=lambda t: t["min"], reverse=True):
                if change_pct >= tier["min"]:
                    variant_key = tier["variant"]
                    break
        else:
            for tier in sorted(tiers, key=lambda t: t["max"]):
                if change_pct <= tier["max"]:
                    variant_key = tier["variant"]
                    break
    else:
        if change_pct > 0:
            pump = quote.get("pump", {})
            if pump and change_pct >= float(pump.get("min_change_pct", 999)):
                variant_key = "pump"
        else:
            crash = quote.get("crash", {})
            if crash and change_pct <= float(crash.get("min_change_pct", -999)):
                variant_key = "crash"

    return variant_key


def _pick_quote_variant(templates: dict, change_pct: float) -> dict:
    quote = templates.get("quote", {})
    key = _quote_variant_key(templates, change_pct)
    if change_pct == 0:
        return dict(quote.get("flat", {}))
    fallback = "up" if change_pct > 0 else "down"
    return dict(quote.get(key, quote.get(fallback, {})))


def _maybe_chance_line(block: dict, **kwargs) -> str:
    if not block:
        return ""
    chance = float(block.get("chance", 0))
    if chance <= 0 or random.random() > chance:
        return ""
    return _line(block, "line", **kwargs)


def _random_best_stock(block: dict) -> str:
    stocks = block.get("best_stocks", [])
    if not stocks:
        return block.get("best_stock_default", "그 종목")
    return random.choice(stocks)


def _maybe_pump_secret_line(templates: dict, change_pct: float) -> str:
    block = templates.get("pump_secret", {})
    if not block:
        return ""
    min_pct = float(block.get("min_change_pct", 15))
    if change_pct < min_pct:
        return ""
    return _maybe_chance_line(block, best_stock=_random_best_stock(block))


def _maybe_after_hours_line(templates: dict) -> str:
    return _maybe_chance_line(templates.get("after_hours", {}))


def _pick_one_line(*candidates: str) -> str:
    """여러 후보 중 비어 있지 않은 문구 하나만 무작위 선택."""
    options = [c.strip() for c in candidates if c and c.strip()]
    return random.choice(options) if options else ""


def _embed_color(up: bool, flat: bool = False) -> discord.Color:
    if flat:
        return discord.Color.light_grey()
    return discord.Color.red() if up else discord.Color.blue()


def build_quote_embed(data: dict, format_price) -> discord.Embed:
    """!주가 응답 임베드."""
    templates = _load_templates()
    change_pct = data["change_pct"]
    up = change_pct > 0
    flat = change_pct == 0
    sign = "+" if up else ""

    t = _pick_quote_variant(templates, change_pct)
    title = _line(t, "title", name=data["name"])
    flavor = _pick_one_line(
        _line(t, "subtitle"),
        _line(t, "field_change_note"),
        _maybe_after_hours_line(templates) if data.get("after_hours") else "",
        _maybe_pump_secret_line(templates, change_pct),
    )

    description = f"`{data['symbol']}`"
    if flavor:
        description = f"{description}\n{flavor}"

    embed = discord.Embed(
        title=title,
        description=description,
        color=_embed_color(up, flat),
    )
    embed.add_field(name="현재가", value=format_price(data["price"], data["currency"]), inline=True)

    change_val = _fmt(
        t.get("field_change", "{sign}{change} ({sign}{change_pct}%)"),
        sign=sign,
        change=format_price(data["change"], data["currency"]),
        change_pct=f"{data['change_pct']:.2f}",
    )
    embed.add_field(
        name=t.get("field_change_name", "등락"),
        value=change_val,
        inline=True,
    )
    embed.add_field(
        name="전일 종가",
        value=format_price(data["prev_close"], data["currency"]),
        inline=True,
    )
    embed.set_footer(text=t.get("footer", "Yahoo Finance · 실시간과 다소 차이가 있을 수 있습니다"))
    return embed


def build_chart_embed(data: dict, format_price) -> discord.Embed:
    """!차트 응답 임베드 (이미지는 호출 쪽에서 첨부)."""
    templates = _load_templates()
    change_pct = data["change_pct"]
    up = change_pct > 0
    flat = change_pct == 0
    sign = "+" if up else ""

    chart = templates.get("chart", {})
    t = chart.get("flat" if flat else ("up" if up else "down"), {})

    title = _line(t, "title", name=data["name"], period=data["period_label"])
    flavor = _pick_one_line(
        _line(t, "subtitle"),
        _line(t, "field_period_note"),
        _maybe_after_hours_line(templates) if data.get("after_hours") else "",
    )

    description = f"`{data['symbol']}`"
    if flavor:
        description = f"{description}\n{flavor}"

    embed = discord.Embed(
        title=title,
        description=description,
        color=_embed_color(up, flat),
    )
    embed.add_field(name="현재가", value=format_price(data["last"], data["currency"]), inline=True)

    period_val = f"{sign}{data['change_pct']:.2f}%"
    embed.add_field(
        name=t.get("field_period_name", "{period} 변동").format(period=data["period_label"]),
        value=period_val,
        inline=True,
    )
    embed.set_footer(text=t.get("footer", "Yahoo Finance"))
    return embed


def build_portfolio_embed(
    user_name: str,
    account: str,
    holdings: list[dict],
    total_eval: float,
    total_profit: float,
    format_price,
) -> discord.Embed:
    """!내주식 응답 임베드."""
    templates = _load_templates()
    up = total_profit >= 0
    flat = total_profit == 0
    sign = "+" if up else ""

    pf = templates.get("portfolio", {})
    t = pf.get("flat" if flat else ("up" if up else "down"), {})

    title = _line(t, "title", user=user_name, account=account)
    subtitle = _line(t, "subtitle", account=account, user=user_name)

    embed = discord.Embed(title=title, description=subtitle, color=_embed_color(up, flat))

    for h in sorted(holdings, key=lambda x: x["eval_amount"], reverse=True)[:20]:
        p_up = h["profit"] >= 0
        p_sign = "+" if p_up else ""
        arrow = "🔺" if h["profit"] > 0 else ("🔻" if h["profit"] < 0 else "➖")
        tmpl = t.get("holding_profit" if p_up else "holding_loss", "{arrow} {sign}{profit} ({sign}{profit_rate}%)")
        profit_line = _fmt(
            tmpl,
            arrow=arrow,
            sign=p_sign,
            profit=format_price(h["profit"], h["currency"]),
            profit_rate=f"{h['profit_rate']:.2f}",
        )
        value_lines = (
            f"{h['quantity']:,.0f}주 · 평가 {format_price(h['eval_amount'], h['currency'])}\n"
            f"{profit_line}"
        )
        embed.add_field(name=h["name"] or h["symbol"], value=value_lines, inline=True)

    profit_note = _line(t, "profit_note", account=account, user=user_name)
    embed.add_field(
        name="─ 합계 ─",
        value=(
            f"{t.get('total_label', '총 평가금액')}: **{format_price(total_eval, 'KRW')}**\n"
            f"{t.get('profit_label', '총 손익')}: {sign}{format_price(total_profit, 'KRW')}"
            + (f"\n*{profit_note}*" if profit_note else "")
        ),
        inline=False,
    )
    embed.set_footer(text=t.get("footer", "토스 Open API"))
    return embed


def not_found_message(query: str) -> str:
    templates = _load_templates()
    return _line(
        {"not_found": templates.get("not_found", "⚠️ `{query}` 종목을 찾을 수 없어요.")},
        "not_found",
        query=query,
    )
