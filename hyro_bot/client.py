from pybit.unified_trading import HTTP
import time

from .candles import INTERVAL_MS
from .config import DEMO_HOST, Settings


class DemoReadOnlyClient:
    """Bybit Demo client limited to public market data and private GET calls."""

    def __init__(self, settings: Settings):
        if not settings.demo:
            raise ValueError("Only Bybit Demo is permitted")
        self.session = HTTP(
            testnet=False,
            demo=True,
            api_key=settings.api_key or None,
            api_secret=settings.api_secret or None,
        )
        self.allowed_symbols = set(settings.symbols)
        # Guard against SDK default changes or accidental endpoint override.
        if getattr(self.session, "endpoint", DEMO_HOST) != DEMO_HOST:
            raise RuntimeError("Unexpected Bybit endpoint; refusing to continue")

    def candles(self, symbol: str, interval: str, limit: int = 100) -> dict:
        if symbol not in getattr(self, "allowed_symbols", {"BTCUSDT", "ETHUSDT"}):
            raise ValueError("Symbol not allowed")
        if interval not in {"5", "15", "60", "240"}:
            raise ValueError("Interval not allowed")
        if not 1 <= limit <= 1000:
            raise ValueError("Limit must be between 1 and 1000")
        return self.session.get_kline(
            category="linear", symbol=symbol, interval=interval, limit=limit
        )

    def candles_range(self, symbol: str, interval: str, start_ms: int,
                      end_ms: int, page_limit: int = 1000) -> dict:
        """Fetch a bounded historical range using Bybit's start/end pagination."""
        if symbol not in getattr(self, "allowed_symbols", {"BTCUSDT", "ETHUSDT"}):
            raise ValueError("Symbol not allowed")
        if interval not in {"5", "15", "60", "240"}:
            raise ValueError("Interval not allowed")
        if start_ms <= 0 or end_ms <= start_ms or not 1 <= page_limit <= 1000:
            raise ValueError("Invalid candle range or page size")
        cursor_end = end_ms
        rows_by_start: dict[str, list[str]] = {}
        server_time = end_ms
        while cursor_end > start_ms:
            # Keep every query bounded to one page's worth of time. This avoids
            # asking the Demo service to scan the full 90-day range repeatedly.
            page_start = max(start_ms, cursor_end - INTERVAL_MS[interval] * page_limit + 1)
            for attempt in range(3):
                try:
                    page = self.session.get_kline(
                        category="linear", symbol=symbol, interval=interval,
                        start=page_start, end=cursor_end, limit=page_limit,
                    )
                    if page.get("retCode") == 0:
                        break
                    code = str(page.get("retCode", ""))
                    if code not in {"10016", "10006", "429"} or attempt == 2:
                        raise RuntimeError("Bybit rejected a historical candle page; retry the backtest later.")
                except Exception as exc:
                    if not any(code in str(exc) for code in ("10016", "10006", "429")) or attempt == 2:
                        raise RuntimeError("Bybit historical candle page failed; retry the backtest later.") from None
                time.sleep(1 + attempt)
            page_rows = page.get("result", {}).get("list", [])
            server_time = max(server_time, int(page.get("time", 0)))
            if not page_rows:
                break
            for row in page_rows:
                rows_by_start[str(row[0])] = row
            oldest = min(int(row[0]) for row in page_rows)
            if oldest <= start_ms or len(page_rows) < page_limit:
                break
            next_end = oldest - 1
            if next_end >= cursor_end:
                raise RuntimeError("Bybit historical candle pagination did not advance")
            cursor_end = next_end
        merged = sorted(rows_by_start.values(), key=lambda row: int(row[0]), reverse=True)
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {"symbol": symbol, "category": "linear", "list": merged},
            "time": server_time,
        }

    def account_info(self) -> dict:
        return self.session.get_account_info()

    def wallet_balance(self) -> dict:
        return self.session.get_wallet_balance(accountType="UNIFIED", coin="USDT")

    def positions(self, symbol: str) -> dict:
        if symbol not in getattr(self, "allowed_symbols", {"BTCUSDT", "ETHUSDT"}):
            raise ValueError("Symbol not allowed")
        return self.session.get_positions(category="linear", symbol=symbol)

    def instrument_info(self, symbol: str) -> dict:
        if symbol not in getattr(self, "allowed_symbols", {"BTCUSDT", "ETHUSDT"}):
            raise ValueError("Symbol not allowed")
        response = self.session.get_instruments_info(category="linear", symbol=symbol)
        instruments = response.get("result", {}).get("list", [])
        if response.get("retCode") != 0 or not instruments:
            raise ValueError(f"Bybit Demo returned no instrument metadata for {symbol}")
        contract = instruments[0]
        if (contract.get("symbol") != symbol or contract.get("status") != "Trading"
                or contract.get("settleCoin") != "USDT"
                or contract.get("contractType") != "LinearPerpetual"):
            raise ValueError(f"{symbol} is not an active USDT linear perpetual on Bybit Demo")
        return contract

    def fee_rates(self, symbol: str) -> dict:
        if symbol not in getattr(self, "allowed_symbols", {"BTCUSDT", "ETHUSDT"}):
            raise ValueError("Symbol not allowed")
        return self.session.get_fee_rates(category="linear", symbol=symbol)
