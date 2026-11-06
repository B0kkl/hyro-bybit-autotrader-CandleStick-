import pytest

from hyro_bot.signals import build_plan
from hyro_bot.candles import Candle
from hyro_bot.strategy import analyze, engulfing_pattern
from hyro_bot.backtest import _exit_trade, run_portfolio_backtest


def test_manual_long_signal_sizes_to_two_percent_risk():
    plan = build_plan({"symbol": "BTCUSDT", "side": "BUY", "entry": 100, "stop_loss": 98, "take_profit": 104}, 5000)
    assert plan.risk_usdt == pytest.approx(100)
    assert plan.quantity == pytest.approx(50)
    assert plan.risk_reward == pytest.approx(2)


def test_rejects_bad_stop_and_low_reward_ratio():
    with pytest.raises(ValueError, match="BUY signal"):
        build_plan({"symbol": "BTCUSDT", "side": "BUY", "entry": 100, "stop_loss": 101, "take_profit": 105}, 5000)
    with pytest.raises(ValueError, match="at least 2.0"):
        build_plan({"symbol": "ETHUSDT", "side": "SELL", "entry": 100, "stop_loss": 102, "take_profit": 97}, 5000)


def test_recognizes_bullish_engulfing():
    previous = Candle(0, 10, 10.5, 8.5, 9, 1, 1)
    current = Candle(1, 8.8, 11, 8.7, 10.8, 1, 1)
    assert engulfing_pattern(previous, current) == "bullish_engulfing"


def test_auto_analysis_fails_closed_with_insufficient_history():
    result = analyze("BTCUSDT", [], [], [], [])
    assert result.status == "NO_SIGNAL"
    assert result.entry is None


def test_backtest_assumes_stop_first_when_stop_and_target_hit_same_bar():
    future = [Candle(10, 100, 103, 97, 101, 1, 1)]
    assert _exit_trade("BUY", 100, 98, 102, future) == (
        0, 98, "stop_and_target_same_bar_stop_assumed"
    )


def test_portfolio_filter_stops_entries_after_daily_loss_cap():
    start = 1_790_000_000_000
    trade1 = {"signal_time_ms": start, "exit_time_ms": start + 60_000,
              "symbol": "SOLUSDT", "gross_r": -1.0, "net_r": None}
    trade2 = {"signal_time_ms": start + 120_000, "exit_time_ms": start + 180_000,
              "symbol": "ADAUSDT", "gross_r": 2.0, "net_r": None}
    result = run_portfolio_backtest(
        [{"trades": [trade1]}, {"trades": [trade2]}], 5000,
        risk_pct=0.1, daily_loss_limit_usdt=10,
    )
    assert result["accepted_trades"] == 1
    assert result["skipped_reasons"] == {"daily_loss_limit": 1}
