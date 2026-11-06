from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .candles import Candle, INTERVAL_MS
from .strategy import analyze


@dataclass(frozen=True)
class BacktestTrade:
    signal_time_ms: int
    exit_time_ms: int
    symbol: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    gross_r: float
    fee_r: float | None
    slippage_r: float | None
    net_r: float | None


def _exit_trade(side: str, entry: float, stop: float, target: float,
                future: list[Candle]) -> tuple[int, float, str] | None:
    for offset, candle in enumerate(future):
        if side == "BUY":
            stop_hit = candle.low <= stop
            target_hit = candle.high >= target
        else:
            stop_hit = candle.high >= stop
            target_hit = candle.low <= target
        # OHLC bars do not reveal intrabar order. If both hit, assume the stop first.
        if stop_hit:
            return offset, stop, "stop" if not target_hit else "stop_and_target_same_bar_stop_assumed"
        if target_hit:
            return offset, target, "target"
    return None


def run_backtest(symbol: str, bars_4h: list[Candle], bars_1h: list[Candle],
                 bars_15m: list[Candle], bars_5m: list[Candle],
                 taker_fee_rate: float | None = None,
                 slippage_bps_per_side: float | None = None) -> dict:
    """Walk forward through closed 5m bars. Results are gross, without costs."""
    trades: list[BacktestTrade] = []
    used_setups: set[int] = set()
    i = 0
    h4_end = h1_end = m15_end = 0
    while i < len(bars_5m):
        event_time = bars_5m[i].start_ms + INTERVAL_MS["5"]
        while h4_end < len(bars_4h) and bars_4h[h4_end].start_ms + INTERVAL_MS["240"] <= event_time:
            h4_end += 1
        while h1_end < len(bars_1h) and bars_1h[h1_end].start_ms + INTERVAL_MS["60"] <= event_time:
            h1_end += 1
        while m15_end < len(bars_15m) and bars_15m[m15_end].start_ms + INTERVAL_MS["15"] <= event_time:
            m15_end += 1
        # The rule needs only 21 higher-timeframe candles and the latest setup pair.
        h4 = bars_4h[max(0, h4_end - 21):h4_end]
        h1 = bars_1h[max(0, h1_end - 21):h1_end]
        m15 = bars_15m[max(0, m15_end - 2):m15_end]
        if m15_end < 2:
            i += 1
            continue
        setup = m15[-1]
        # Confirmation must come after setup formation, never from an overlapping bar.
        if event_time <= setup.start_ms + INTERVAL_MS["15"] or setup.start_ms in used_setups:
            i += 1
            continue
        result = analyze(symbol, h4, h1, m15, [bars_5m[i]])
        if result.status != "SIGNAL_ONLY" or result.entry is None:
            i += 1
            continue
        used_setups.add(setup.start_ms)
        risk = abs(result.entry - result.stop_loss)
        side = "BUY" if result.take_profit > result.entry else "SELL"
        exit_result = _exit_trade(side, result.entry, result.stop_loss,
                                  result.take_profit, bars_5m[i + 1:])
        if exit_result is None:
            # Open trades are omitted from completed performance statistics.
            break
        exit_offset, exit_price, reason = exit_result
        gross_r = ((exit_price - result.entry) if side == "BUY" else (result.entry - exit_price)) / risk
        fee_r = taker_fee_rate * (result.entry + exit_price) / risk if taker_fee_rate is not None else None
        slippage_r = (slippage_bps_per_side / 10000) * (result.entry + exit_price) / risk if slippage_bps_per_side is not None else None
        net_r = gross_r - fee_r - slippage_r if fee_r is not None and slippage_r is not None else None
        exit_bar = bars_5m[i + 1 + exit_offset]
        exit_time = exit_bar.start_ms + INTERVAL_MS["5"]
        trades.append(BacktestTrade(event_time, exit_time, symbol, side, result.entry,
                                    result.stop_loss, result.take_profit,
                                    exit_price, reason, gross_r, fee_r, slippage_r, net_r))
        # The next trade may start only after the exit bar.
        i += exit_offset + 2
    wins = sum(t.gross_r > 0 for t in trades)
    return {
        "symbol": symbol,
        "completed_trades": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate_pct": (wins / len(trades) * 100) if trades else 0.0,
        "gross_total_r": sum(t.gross_r for t in trades),
        "gross_expectancy_r": (sum(t.gross_r for t in trades) / len(trades)) if trades else 0.0,
        "net_total_r": sum(t.net_r for t in trades) if trades and all(t.net_r is not None for t in trades) else None,
        "history_bars": {"4h": len(bars_4h), "1h": len(bars_1h), "15m": len(bars_15m), "5m": len(bars_5m)},
        "first_5m_candle_ms": bars_5m[0].start_ms if bars_5m else None,
        "last_5m_candle_ms": bars_5m[-1].start_ms if bars_5m else None,
        "taker_fee_rate": taker_fee_rate,
        "slippage_bps_per_side": slippage_bps_per_side,
        "net_r_available": taker_fee_rate is not None and slippage_bps_per_side is not None,
        "gross_metrics_include_costs": False,
        "net_metrics_include_fee_slippage": taker_fee_rate is not None and slippage_bps_per_side is not None,
        "funding_included": False,
        "same_bar_stop_target_rule": "assume stop fills first",
        "trades": [asdict(t) for t in trades],
    }


def run_portfolio_backtest(reports: list[dict], starting_balance: float,
                           risk_pct: float = 2.0, max_positions: int = 1,
                           max_trades_per_day: int = 3,
                           daily_loss_limit_usdt: float = 50.0) -> dict:
    """Apply provisional account-level limits to per-symbol candidate trades."""
    if min(starting_balance, risk_pct, max_positions, max_trades_per_day,
           daily_loss_limit_usdt) <= 0:
        raise ValueError("Portfolio limits and starting balance must be positive")
    if risk_pct > 2.0:
        raise ValueError("Portfolio risk per trade cannot exceed the 2% trial cap")
    candidates = [trade for report in reports for trade in report.get("trades", [])]
    candidates.sort(key=lambda trade: (trade["signal_time_ms"], trade["symbol"]))
    risk_usdt = starting_balance * risk_pct / 100
    active: list[tuple[int, float, str]] = []
    daily_realized: dict[str, float] = {}
    daily_entries: dict[str, int] = {}
    accepted: list[dict] = []
    skipped: dict[str, int] = {}
    for trade in candidates:
        entry_time = trade["signal_time_ms"]
        active.sort(key=lambda item: item[0])
        still_open = []
        for exit_time, pnl_usdt, exit_day in active:
            if exit_time <= entry_time:
                daily_realized[exit_day] = daily_realized.get(exit_day, 0.0) + pnl_usdt
            else:
                still_open.append((exit_time, pnl_usdt, exit_day))
        active = still_open
        entry_day = datetime.fromtimestamp(entry_time / 1000, tz=timezone.utc).date().isoformat()
        if daily_realized.get(entry_day, 0.0) - risk_usdt <= -daily_loss_limit_usdt:
            skipped["daily_loss_limit"] = skipped.get("daily_loss_limit", 0) + 1
            continue
        if daily_entries.get(entry_day, 0) >= max_trades_per_day:
            skipped["max_trades_per_day"] = skipped.get("max_trades_per_day", 0) + 1
            continue
        if len(active) >= max_positions:
            skipped["max_open_positions"] = skipped.get("max_open_positions", 0) + 1
            continue
        r_value = trade["net_r"] if trade.get("net_r") is not None else trade["gross_r"]
        pnl_usdt = r_value * risk_usdt
        exit_time = trade["exit_time_ms"]
        exit_day = datetime.fromtimestamp(exit_time / 1000, tz=timezone.utc).date().isoformat()
        active.append((exit_time, pnl_usdt, exit_day))
        daily_entries[entry_day] = daily_entries.get(entry_day, 0) + 1
        accepted.append(trade)
    for _, pnl_usdt, exit_day in active:
        daily_realized[exit_day] = daily_realized.get(exit_day, 0.0) + pnl_usdt
    net_available = all(t.get("net_r") is not None for t in accepted)
    return {
        "candidate_trades": len(candidates),
        "accepted_trades": len(accepted),
        "skipped_trades": len(candidates) - len(accepted),
        "skipped_reasons": skipped,
        "risk_pct_per_trade": risk_pct,
        "risk_usdt_per_trade_fixed": risk_usdt,
        "max_open_positions": max_positions,
        "max_trades_per_day_utc": max_trades_per_day,
        "daily_loss_limit_usdt": daily_loss_limit_usdt,
        "daily_loss_basis": "realized exits; intraday unrealized drawdown is not modeled",
        "daily_loss_uses": "fee/slippage-adjusted R where available, otherwise gross R",
        "funding_included": False,
        "gross_total_r_accepted": sum(t["gross_r"] for t in accepted),
        "net_total_r_accepted": sum(t["net_r"] for t in accepted) if net_available else None,
        "net_usdt_accepted": sum(t["net_r"] * risk_usdt for t in accepted) if net_available else None,
        "gross_usdt_accepted": sum(t["gross_r"] * risk_usdt for t in accepted),
        "trades": accepted,
    }
