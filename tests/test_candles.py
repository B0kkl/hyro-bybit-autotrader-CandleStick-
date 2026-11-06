import pytest

from hyro_bot.candles import completed_candles


def test_excludes_open_candle_and_sorts_oldest_first():
    start = 1_800_000_000_000
    response = {
        "retCode": 0,
        "time": start + 16 * 60_000,
        "result": {"list": [
            [str(start + 15 * 60_000), "2", "3", "1", "2.5", "20", "40"],
            [str(start), "1", "2", "0.5", "1.5", "10", "15"],
        ]},
    }
    bars = completed_candles(response, "15")
    assert [bar.start_ms for bar in bars] == [start]
    assert bars[0].close == 1.5


def test_rejects_bybit_errors():
    with pytest.raises(ValueError, match="request failed"):
        completed_candles({"retCode": 10001, "retMsg": "bad request"}, "15")
