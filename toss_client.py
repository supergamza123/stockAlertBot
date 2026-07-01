"""토스증권 Open API 연동 클라이언트.

내 증권계좌의 보유 종목/평가금액을 조회하기 위한 최소 기능 클라이언트입니다.

인증: OAuth 2.0 Client Credentials Grant
Base URL: https://openapi.tossinvest.com
문서: https://developers.tossinvest.com/docs

⚠️ client_id / client_secret 은 실제 증권계좌에 접근하는 비밀키입니다.
   코드에 하드코딩하지 말고 .env 로만 관리하세요.

참고: 토스 Open API는 순차 오픈/개선 중이라 응답 필드명이 바뀔 수 있습니다.
      보유종목 파싱은 여러 후보 키를 시도하도록 방어적으로 작성되어 있으며,
      실제 응답과 다르면 _normalize_holding() 의 키 목록만 조정하면 됩니다.
"""

import time

import requests

TOSS_BASE = "https://openapi.tossinvest.com"


class TossAPIError(Exception):
    """토스 API 호출 실패."""


class TossClient:
    def __init__(self, client_id: str, client_secret: str, timeout: int = 10):
        if not client_id or not client_secret:
            raise TossAPIError("TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 가 설정되지 않았습니다.")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # ── 인증 ──────────────────────────────────────────────
    def _get_token(self) -> str:
        # 만료 30초 전이면 재발급
        if self._token and time.time() < self._token_expiry - 30:
            return self._token

        try:
            resp = requests.post(
                f"{TOSS_BASE}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise TossAPIError(f"토큰 요청 실패: {e}") from e

        if resp.status_code != 200:
            raise TossAPIError(f"토큰 발급 실패 (HTTP {resp.status_code}): {resp.text[:200]}")

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise TossAPIError(f"응답에 access_token 이 없습니다: {data}")

        self._token = token
        self._token_expiry = time.time() + int(data.get("expires_in", 1800))
        return token

    def _headers(self, account: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        if account:
            headers["X-Tossinvest-Account"] = account
        return headers

    def _get(self, path: str, account: str | None = None) -> dict:
        try:
            resp = requests.get(
                f"{TOSS_BASE}{path}",
                headers=self._headers(account),
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise TossAPIError(f"요청 실패({path}): {e}") from e

        if resp.status_code == 401:
            raise TossAPIError("인증 실패(401). client_id/secret 또는 권한을 확인하세요.")
        if resp.status_code != 200:
            raise TossAPIError(f"API 오류({path}, HTTP {resp.status_code}): {resp.text[:200]}")
        return resp.json()

    # ── 조회 ──────────────────────────────────────────────
    def get_accounts(self) -> list[dict]:
        """보유 계좌 목록 조회."""
        data = self._get("/v1/accounts")
        return _as_list(data, ("accounts", "data", "result"))

    def get_holdings(self, account: str) -> list[dict]:
        """특정 계좌의 보유 종목 조회 (정규화된 리스트 반환)."""
        data = self._get("/v1/accounts/holdings", account=account)
        raw_list = _as_list(data, ("holdings", "stocks", "data", "result"))
        return [_normalize_holding(item) for item in raw_list]


# ── 유틸: 다양한 응답 구조/필드명에 대응 ─────────────────────
def _as_list(data, candidate_keys: tuple[str, ...]) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in candidate_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for inner in ("items", "list", "content"):
                    if isinstance(value.get(inner), list):
                        return value[inner]
    return []


def _pick(item: dict, keys: tuple[str, ...], default=None):
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_holding(item: dict) -> dict:
    """토스 응답의 보유종목 1건을 공통 형식으로 변환.

    응답 필드명이 확정되지 않아 여러 후보 키를 시도합니다.
    실제 스펙 확인 후 이 부분만 맞춰주면 됩니다.
    """
    name = _pick(item, ("name", "stockName", "productName", "koreanName"), "")
    symbol = _pick(item, ("symbol", "code", "stockCode", "shortCode", "isin"), "")
    quantity = _to_float(_pick(item, ("quantity", "qty", "holdingQuantity", "balanceQty")))
    avg_price = _to_float(_pick(item, ("averagePrice", "avgPrice", "purchasePrice", "buyPrice")))
    cur_price = _to_float(_pick(item, ("currentPrice", "price", "lastPrice", "closePrice")))
    eval_amount = _to_float(
        _pick(item, ("evaluationAmount", "evalAmount", "valuationAmount", "currentAmount", "amount"))
    )
    profit = _to_float(_pick(item, ("profitLoss", "profit", "evalProfit", "gainLoss")))
    profit_rate = _to_float(_pick(item, ("profitLossRate", "profitRate", "returnRate", "rate")))
    currency = _pick(item, ("currency", "currencyCode"), "KRW")

    # 평가금액이 없으면 수량 * 현재가로 보완
    if not eval_amount and quantity and cur_price:
        eval_amount = quantity * cur_price
    # 손익률이 없고 매입가/현재가가 있으면 계산
    if not profit_rate and avg_price and cur_price:
        profit_rate = (cur_price - avg_price) / avg_price * 100

    return {
        "name": name or symbol,
        "symbol": symbol,
        "quantity": quantity,
        "avg_price": avg_price,
        "current_price": cur_price,
        "eval_amount": eval_amount,
        "profit": profit,
        "profit_rate": profit_rate,
        "currency": currency,
        "_raw": item,
    }
