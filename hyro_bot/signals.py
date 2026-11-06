from dataclasses import dataclass
import json
from pathlib import Path


DEFAULT_ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT"}


@dataclass(frozen=True)
class TradePlan:
    source: str
    symbol: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    quantity: float
    risk_usdt: float


def build_plan(data: dict, equity_usdt: float, risk_pct: float = 2.0,
               allowed_symbols: set[str] | None = None) -> TradePlan:
    """Validate a proposed signal and calculate risk-based linear-contract size."""
    try:
        symbol = str(data["symbol"]).upper()
        side = str(data["side"]).upper()
        entry = float(data["entry"])
        stop = float(data["stop_loss"])
        target = float(data["take_profit"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Signal requires symbol, side, entry, stop_loss and take_profit") from exc
    if symbol not in (allowed_symbols or DEFAULT_ALLOWED_SYMBOLS) or side not in {"BUY", "SELL"}:
        raise ValueError("Signal symbol or side is not allowed")
    if min(entry, stop, target, equity_usdt, risk_pct) <= 0:
        raise ValueError("Prices, equity and risk percentage must be positive")
    if risk_pct > 2.0:
        raise ValueError("Risk per signal cannot exceed the 2% trial cap")
    if side == "BUY":
        if not stop < entry < target:
            raise ValueError("BUY signal requires stop_loss < entry < take_profit")
    elif not target < entry < stop:
        raise ValueError("SELL signal requires take_profit < entry < stop_loss")
    risk_distance = abs(entry - stop)
    reward_risk = abs(target - entry) / risk_distance
    if reward_risk < 2.0:
        raise ValueError("Signal reward-to-risk must be at least 2.0")
    risk_usdt = equity_usdt * risk_pct / 100
    quantity = risk_usdt / risk_distance
    return TradePlan(
        source=str(data.get("source", "manual")), symbol=symbol, side=side,
        entry=entry, stop_loss=stop, take_profit=target,
        risk_reward=reward_risk, quantity=quantity, risk_usdt=risk_usdt,
    )


def load_manual_signal(path: Path, require_enabled: bool = True) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Signal file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Signal file must contain valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Manual signal file must contain a JSON object")
    if require_enabled and data.get("enabled") is not True:
        raise ValueError("Manual signal is disabled; set enabled to true to preview it")
    return data
