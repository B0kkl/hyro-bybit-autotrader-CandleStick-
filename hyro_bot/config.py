from dataclasses import dataclass
import os
import re

DEMO_HOST = "https://api-demo.bybit.com"
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT")


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    api_secret: str = ""
    demo: bool = True
    trading_enabled: bool = False
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    backtest_slippage_bps: float | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        # Refuse non-demo configuration rather than permit accidental live access.
        demo_value = os.getenv("BYBIT_DEMO", "true").strip().lower()
        if demo_value != "true":
            raise ValueError("Only Bybit Demo is permitted; set BYBIT_DEMO=true")
        if os.getenv("TRADING_ENABLED", "false").strip().lower() != "false":
            raise ValueError("Order execution is not implemented in this starter")
        symbols_raw = os.getenv("TRADING_SYMBOLS", ",".join(DEFAULT_SYMBOLS))
        symbols = tuple(dict.fromkeys(s.strip().upper() for s in symbols_raw.split(",") if s.strip()))
        if not symbols:
            raise ValueError("TRADING_SYMBOLS must contain at least one USDT perpetual symbol")
        if len(symbols) > 10:
            raise ValueError("Configure no more than 10 symbols at a time")
        if any(not re.fullmatch(r"[A-Z0-9]{2,20}USDT", symbol) for symbol in symbols):
            raise ValueError("Symbols must use the BASEUSDT format")
        slip_raw = os.getenv("BACKTEST_SLIPPAGE_BPS", "").strip()
        try:
            slippage = float(slip_raw) if slip_raw else None
        except ValueError as exc:
            raise ValueError("BACKTEST_SLIPPAGE_BPS must be a non-negative number") from exc
        if slippage is not None and slippage < 0:
            raise ValueError("BACKTEST_SLIPPAGE_BPS must be a non-negative number")
        return cls(
            api_key=os.getenv("BYBIT_API_KEY", "").strip(),
            api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
            symbols=symbols,
            backtest_slippage_bps=slippage,
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)
