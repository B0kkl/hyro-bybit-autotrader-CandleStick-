from dataclasses import dataclass

from .candles import Candle


@dataclass(frozen=True)
class Analysis:
    symbol: str
    bias_4h: str
    structure_1h: str
    pattern_15m: str
    confirmed_5m: bool
    status: str
    reason: str
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


def engulfing_pattern(previous: Candle, current: Candle) -> str | None:
    prev_bear = previous.close < previous.open
    prev_bull = previous.close > previous.open
    curr_bull = current.close > current.open
    curr_bear = current.close < current.open
    if prev_bear and curr_bull and current.open <= previous.close and current.close >= previous.open:
        return "bullish_engulfing"
    if prev_bull and curr_bear and current.open >= previous.close and current.close <= previous.open:
        return "bearish_engulfing"
    return None


def _breakout_direction(bars: list[Candle], lookback: int = 20) -> str:
    if len(bars) < lookback + 1:
        return "insufficient_data"
    prior = bars[-lookback - 1:-1]
    latest = bars[-1]
    if latest.close > max(c.high for c in prior):
        return "bullish"
    if latest.close < min(c.low for c in prior):
        return "bearish"
    return "neutral"


def analyze(symbol: str, bars_4h: list[Candle], bars_1h: list[Candle],
            bars_15m: list[Candle], bars_5m: list[Candle]) -> Analysis:
    bias = _breakout_direction(bars_4h)
    structure = _breakout_direction(bars_1h)
    if "insufficient_data" in {bias, structure} or len(bars_15m) < 2 or not bars_5m:
        return Analysis(symbol, bias, structure, "none", False, "NO_SIGNAL", "Need more completed candles")
    pattern = engulfing_pattern(bars_15m[-2], bars_15m[-1])
    if not pattern:
        return Analysis(symbol, bias, structure, "none", False, "NO_SIGNAL", "No engulfing setup on the latest completed 15m candle")
    direction = "bullish" if pattern.startswith("bullish") else "bearish"
    confirm = bars_5m[-1].close > bars_15m[-1].high if direction == "bullish" else bars_5m[-1].close < bars_15m[-1].low
    if bias != direction or structure != direction or not confirm:
        return Analysis(symbol, bias, structure, pattern, confirm, "NO_SIGNAL", "Higher-timeframe alignment or 5m breakout confirmation missing")
    entry = bars_5m[-1].close
    stop = bars_15m[-1].low if direction == "bullish" else bars_15m[-1].high
    risk = abs(entry - stop)
    if risk <= 0:
        return Analysis(symbol, bias, structure, pattern, confirm, "NO_SIGNAL", "Invalid stop distance")
    target = entry + 2 * risk if direction == "bullish" else entry - 2 * risk
    side = "BUY" if direction == "bullish" else "SELL"
    return Analysis(symbol, bias, structure, pattern, confirm, "SIGNAL_ONLY", "All rules aligned; no order was sent", entry, stop, target)
