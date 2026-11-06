from dataclasses import dataclass


INTERVAL_MS = {"5": 5 * 60_000, "15": 15 * 60_000, "60": 60 * 60_000, "240": 240 * 60_000}


@dataclass(frozen=True)
class Candle:
    start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


def completed_candles(response: dict, interval: str) -> list[Candle]:
    """Parse Bybit V5 klines chronologically and exclude candles not yet closed."""
    if interval not in INTERVAL_MS:
        raise ValueError("Unsupported candle interval")
    if response.get("retCode") != 0:
        raise ValueError(f"Bybit candle request failed: {response.get('retMsg', 'unknown error')}")
    result = response.get("result") or {}
    try:
        server_time = int(response["time"])
        rows = result["list"]
        if not isinstance(rows, list):
            raise TypeError
        parsed = [Candle(int(r[0]), *(float(v) for v in r[1:7])) for r in rows]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValueError("Malformed Bybit candle response") from exc
    closed = [c for c in parsed if c.start_ms + INTERVAL_MS[interval] <= server_time]
    return sorted(closed, key=lambda candle: candle.start_ms)
