"""원하는 주식의 현재가와 등락율을 알려주는 디스코드 봇.

한국(KOSPI/KOSDAQ) 및 미국 주식을 모두 지원합니다.
데이터 출처: yfinance (Yahoo Finance)

사용 예시:
    !주가 삼성전자
    !주가 005930
    !주가 AAPL
    !주가 TSLA
"""

import os
import io
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yfinance as yf
import matplotlib

matplotlib.use("Agg")  # GUI 없는 환경에서 이미지 생성용
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager

from toss_client import TossClient, TossAPIError
import store
from stock_map import lookup_code, reload_name_map
from market_session import is_regular_market_hours
from callisto_style import (
    build_quote_embed,
    build_chart_embed,
    build_portfolio_embed,
    not_found_message,
)


def _setup_korean_font() -> bool:
    """시스템에 있는 한글 폰트를 찾아 matplotlib에 적용. 성공 시 True."""
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Gulim"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


HAS_KOREAN_FONT = _setup_korean_font()

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("COMMAND_PREFIX", "!")

# 봇 운영자 본인용 기본 키 (선택). 사용자별 !등록 키가 우선합니다.
ENV_TOSS_CLIENT_ID = os.getenv("TOSS_CLIENT_ID")
ENV_TOSS_CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET")
ENV_TOSS_ACCOUNT = os.getenv("TOSS_ACCOUNT")

_toss_clients: dict[str, TossClient] = {}


def resolve_credentials(user_id: int | str) -> dict | None:
    """사용자별 등록 키를 우선 조회하고, 없으면 .env 기본 키로 폴백."""
    creds = store.get_credentials(user_id)
    if creds:
        return creds
    if ENV_TOSS_CLIENT_ID and ENV_TOSS_CLIENT_SECRET:
        return {
            "client_id": ENV_TOSS_CLIENT_ID,
            "client_secret": ENV_TOSS_CLIENT_SECRET,
            "account": ENV_TOSS_ACCOUNT or "",
        }
    return None


def load_portfolio(user_id: int | str) -> dict:
    """해당 사용자의 토스 키로 계좌 보유종목을 조회해 요약 반환. (동기 함수)"""
    creds = resolve_credentials(user_id)
    if creds is None:
        raise TossAPIError(
            "등록된 토스 API 키가 없어요. 봇에게 DM으로 `!등록 <client_id> <client_secret>` 을 보내 등록해 주세요."
        )

    client = _toss_clients.get(str(user_id))
    if client is None:
        client = TossClient(creds["client_id"], creds["client_secret"])
        _toss_clients[str(user_id)] = client

    account = creds.get("account")
    if not account:
        accounts = client.get_accounts()
        if not accounts:
            raise TossAPIError("연결된 계좌를 찾을 수 없습니다.")
        first = accounts[0]
        account = first.get("accountNumber") or first.get("account") or first.get("id") or first.get("number")
        if not account:
            raise TossAPIError(f"계좌번호를 확인할 수 없습니다: {first}")

    holdings = client.get_holdings(str(account))
    total_eval = sum(h["eval_amount"] for h in holdings)
    total_profit = sum(h["profit"] for h in holdings)
    return {
        "account": account,
        "holdings": holdings,
        "total_eval": total_eval,
        "total_profit": total_profit,
    }

# 종목명/별칭 → 코드 매핑: data/kr_aliases.json (수동) + data/kr_stocks.json (자동)
# 별칭 추가: data/kr_aliases.json 편집 후 bot-restart


def resolve_symbols(query: str) -> list[str]:
    """사용자 입력을 yfinance 티커 후보 목록으로 변환."""
    q = query.strip()
    code = lookup_code(q)

    if code:
        if code.isdigit() and len(code) == 6:
            return [f"{code}.KS", f"{code}.KQ"]
        return [code.upper()]

    if q.isdigit() and len(q) == 6:
        return [f"{q}.KS", f"{q}.KQ"]

    return [q.upper()]


def fetch_quote(query: str) -> dict | None:
    """티커 후보들을 순서대로 조회해서 첫 성공 결과를 반환."""
    for symbol in resolve_symbols(query):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)

            if price is None or prev_close is None or prev_close == 0:
                continue

            change = price - prev_close
            change_pct = (change / prev_close) * 100
            currency = getattr(info, "currency", None) or ""

            # 종목명 가져오기 (실패해도 무시)
            name = symbol
            try:
                full_info = ticker.info
                name = full_info.get("longName") or full_info.get("shortName") or symbol
            except Exception:
                pass

            return {
                "symbol": symbol,
                "name": name,
                "price": price,
                "prev_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "currency": currency,
                "after_hours": not is_regular_market_hours(symbol),
            }
        except Exception:
            continue
    return None


def format_price(value: float, currency: str) -> str:
    if currency == "KRW":
        return f"{value:,.0f}원"
    if currency == "USD":
        return f"${value:,.2f}"
    return f"{value:,.2f} {currency}".strip()


# 차트 기간 별칭 -> (yfinance period, interval, 표시 이름)
PERIOD_OPTIONS = {
    "1d": ("1d", "5m", "1일"),
    "5d": ("5d", "30m", "5일"),
    "1w": ("5d", "30m", "5일"),
    "1mo": ("1mo", "1d", "1개월"),
    "1m": ("1mo", "1d", "1개월"),
    "3mo": ("3mo", "1d", "3개월"),
    "3m": ("3mo", "1d", "3개월"),
    "6mo": ("6mo", "1d", "6개월"),
    "6m": ("6mo", "1d", "6개월"),
    "1y": ("1y", "1d", "1년"),
    "1년": ("1y", "1d", "1년"),
    "ytd": ("ytd", "1d", "올해"),
    "5y": ("5y", "1wk", "5년"),
    "max": ("max", "1mo", "전체"),
}


def generate_chart(query: str, period_key: str = "3mo") -> tuple[io.BytesIO, dict] | None:
    """종목의 주가 추이 차트를 PNG 이미지(BytesIO)로 생성해서 반환."""
    period, interval, period_label = PERIOD_OPTIONS.get(
        period_key.lower(), PERIOD_OPTIONS["3mo"]
    )

    for symbol in resolve_symbols(query):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                continue

            closes = hist["Close"].dropna()
            if closes.empty:
                continue

            currency = getattr(ticker.fast_info, "currency", None) or ""

            name = symbol
            try:
                full_info = ticker.info
                name = full_info.get("shortName") or full_info.get("longName") or symbol
            except Exception:
                pass

            first = closes.iloc[0]
            last = closes.iloc[-1]
            up = last >= first
            # 한국식 색상: 상승 빨강, 하락 파랑
            line_color = "#d32f2f" if up else "#1976d2"

            fig, ax = plt.subplots(figsize=(10, 5), dpi=110)
            ax.plot(closes.index, closes.values, color=line_color, linewidth=2)
            ax.fill_between(closes.index, closes.values, closes.min(), color=line_color, alpha=0.08)

            chart_period = period_label if HAS_KOREAN_FONT else period
            ax.set_title(f"{symbol}  ·  {chart_period}", fontsize=14, fontweight="bold")
            ax.grid(True, linestyle="--", alpha=0.3)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

            # 통화 기호 y축 표기
            symbol_prefix = "₩" if currency == "KRW" else ("$" if currency == "USD" else "")
            ax.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda v, _: f"{symbol_prefix}{v:,.0f}")
            )
            fig.autofmt_xdate()
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())

            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            change_pct = ((last - first) / first) * 100 if first else 0.0
            return buf, {
                "symbol": symbol,
                "name": name,
                "currency": currency,
                "first": float(first),
                "last": float(last),
                "change_pct": change_pct,
                "period_label": period_label,
                "up": up,
                "after_hours": not is_regular_market_hours(symbol),
            }
        except Exception:
            continue
    return None


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user} (명령어 접두사: {PREFIX})")


@bot.command(name="주가", aliases=["주식", "stock", "price"])
async def stock(ctx: commands.Context, *, query: str = ""):
    """주식의 현재가와 등락율을 조회합니다. 예: !주가 삼성전자 / !주가 AAPL"""
    if not query:
        await ctx.send(f"❓ 종목을 입력해 주세요. 예: `{PREFIX}주가 삼성전자` 또는 `{PREFIX}주가 AAPL`")
        return

    async with ctx.typing():
        # yfinance는 동기 함수이므로 별도 스레드에서 실행
        data = await asyncio.to_thread(fetch_quote, query)

    if data is None:
        await ctx.send(not_found_message(query))
        return

    embed = build_quote_embed(data, format_price)
    await ctx.send(embed=embed)


@bot.command(name="차트", aliases=["chart", "그래프", "graph"])
async def chart(ctx: commands.Context, query: str = "", period_key: str = "3mo"):
    """주가 추이 그래프를 보여줍니다. 예: !차트 삼성전자 6mo / !차트 AAPL 1y"""
    if not query:
        await ctx.send(
            f"❓ 종목을 입력해 주세요. 예: `{PREFIX}차트 삼성전자 3mo` 또는 `{PREFIX}차트 AAPL 1y`\n"
            "기간: 1d, 5d, 1mo, 3mo, 6mo, 1y, ytd, 5y, max"
        )
        return

    async with ctx.typing():
        result = await asyncio.to_thread(generate_chart, query, period_key)

    if result is None:
        await ctx.send(not_found_message(query))
        return

    buf, data = result
    embed = build_chart_embed(data, format_price)

    file = discord.File(buf, filename="chart.png")
    embed.set_image(url="attachment://chart.png")
    embed.set_footer(text="데이터: Yahoo Finance")

    await ctx.send(embed=embed, file=file)


@bot.command(name="등록", aliases=["register", "키등록"])
async def register(ctx: commands.Context, client_id: str = "", client_secret: str = "", account: str = ""):
    """토스 API 키를 등록합니다. 보안을 위해 봇에게 DM으로만 보내세요.
    사용법(DM): !등록 <client_id> <client_secret> [계좌번호]
    """
    # 공개 채널에 키가 노출되지 않도록 방어
    if ctx.guild is not None:
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass
        await ctx.send(
            f"🔒 {ctx.author.mention} 보안을 위해 키 등록은 **DM(봇에게 개인 메시지)** 으로만 받아요.\n"
            "저에게 직접 DM으로 `!등록 <client_id> <client_secret>` 을 보내주세요. (방금 메시지는 삭제했어요)"
        )
        return

    if not client_id or not client_secret:
        await ctx.send(
            "사용법: `!등록 <client_id> <client_secret> [계좌번호]`\n"
            "토스증권 WTS(PC 웹) → 설정 → Open API 에서 키를 발급받을 수 있어요."
        )
        return

    store.save_credentials(ctx.author.id, client_id, client_secret, account)
    _toss_clients.pop(str(ctx.author.id), None)  # 캐시 무효화
    await ctx.send(
        "✅ 키를 안전하게 암호화해서 저장했어요. 이제 아무 채널에서나 `!내주식` 으로 본인 계좌를 조회할 수 있어요.\n"
        "등록을 해제하려면 `!등록해제` 를 보내세요."
    )


@bot.command(name="등록해제", aliases=["unregister", "키삭제", "삭제"])
async def unregister(ctx: commands.Context):
    """등록한 토스 API 키를 삭제합니다."""
    removed = store.delete_credentials(ctx.author.id)
    _toss_clients.pop(str(ctx.author.id), None)
    if removed:
        await ctx.send("🗑️ 등록된 키를 삭제했어요.")
    else:
        await ctx.send("등록된 키가 없어요.")


@bot.command(name="내주식", aliases=["포트폴리오", "portfolio", "잔고", "내계좌"])
async def portfolio(ctx: commands.Context):
    """토스증권 계좌의 보유 종목과 평가금액을 조회합니다. (본인 토스 API 키 필요)"""
    if resolve_credentials(ctx.author.id) is None:
        await ctx.send(
            "⚠️ 아직 토스 API 키가 등록되지 않았어요.\n"
            "봇에게 **DM**으로 `!등록 <client_id> <client_secret>` 을 보내 등록해 주세요.\n"
            "키는 토스증권 WTS(PC 웹) → 설정 → Open API 에서 발급받을 수 있어요."
        )
        return

    async with ctx.typing():
        try:
            data = await asyncio.to_thread(load_portfolio, ctx.author.id)
        except TossAPIError as e:
            await ctx.send(f"⚠️ 조회 실패: {e}")
            return
        except Exception as e:
            await ctx.send(f"⚠️ 예상치 못한 오류: {e}")
            return

    holdings = data["holdings"]
    if not holdings:
        await ctx.send("📭 보유 중인 종목이 없어요.")
        return

    embed = build_portfolio_embed(
        ctx.author.display_name,
        data["account"],
        holdings,
        data["total_eval"],
        data["total_profit"],
        format_price,
    )
    await ctx.send(embed=embed)


@bot.command(name="종목갱신", aliases=["reload-stocks"])
@commands.is_owner()
async def reload_stocks(ctx: commands.Context):
    """JSON 종목 매핑을 다시 읽습니다. (봇 소유자 전용)"""
    await asyncio.to_thread(reload_name_map)
    await ctx.send("✅ 종목 매핑을 다시 불러왔어요. (`data/kr_aliases.json`, `data/kr_stocks.json`)")


@bot.command(name="도움말", aliases=["help", "명령어"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(
        title="📈 주식 봇 명령어",
        description="*마에스트로 칼리스토가 시세를 읽어 드립니다. 팔 타이밍은… 보장 못 합니다.*",
        color=discord.Color(0x4A90D9),
    )
    embed.add_field(
        name=f"{PREFIX}주가 <종목>",
        value=(
            "주식의 현재가와 등락율을 알려줍니다.\n"
            f"예) `{PREFIX}주가 삼성전자`, `{PREFIX}주가 005930`, `{PREFIX}주가 AAPL`"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{PREFIX}차트 <종목> [기간]",
        value=(
            "주가 추이 그래프를 보여줍니다. 기간: 1d, 5d, 1mo, 3mo, 6mo, 1y, ytd, 5y, max\n"
            f"예) `{PREFIX}차트 삼성전자 6mo`, `{PREFIX}차트 AAPL 1y`"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{PREFIX}등록 <client_id> <client_secret> [계좌번호]",
        value=(
            "🔒 **봇에게 DM으로만** 본인 토스 API 키를 등록합니다.\n"
            "등록하면 각자 자기 계좌만 조회돼요. (`!등록해제`로 삭제)"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{PREFIX}내주식",
        value="등록한 토스 계좌의 보유 종목과 평가금액/손익을 보여줍니다.",
        inline=False,
    )
    embed.add_field(
        name="종목명 검색",
        value=(
            "한국: **공식 종목명** 또는 **별칭**(삼전, 하이닉스 등) · **6자리 코드**\n"
            "미국: **티커** 또는 **별칭**(테슬라, 애플 등) · 띄어쓰기/대소문자 무관"
        ),
        inline=False,
    )
    embed.add_field(name=f"{PREFIX}도움말", value="이 도움말을 표시합니다.", inline=False)
    await ctx.send(embed=embed)


def main():
    if not TOKEN:
        raise SystemExit(
            "❌ DISCORD_TOKEN이 설정되지 않았습니다.\n"
            ".env.example을 .env로 복사한 뒤 봇 토큰을 입력하세요."
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
