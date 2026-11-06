from hyro_bot.client import DemoReadOnlyClient


class FakeSession:
    def __init__(self):
        self.calls = []

    def get_kline(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            rows = [["9000", "1", "2", "0", "1", "1", "1"],
                    ["8000", "1", "2", "0", "1", "1", "1"]]
        else:
            rows = [["7000", "1", "2", "0", "1", "1", "1"]]
        return {"retCode": 0, "time": 20000, "result": {"list": rows}}


def test_historical_candles_are_paginated_and_deduplicated():
    client = object.__new__(DemoReadOnlyClient)
    client.session = FakeSession()
    result = client.candles_range("BTCUSDT", "5", 6000, 10000, page_limit=2)
    assert [int(row[0]) for row in result["result"]["list"]] == [9000, 8000, 7000]
    assert len(client.session.calls) == 2
    assert client.session.calls[1]["end"] == 7999


def test_historical_candle_request_retries_transient_server_error(monkeypatch):
    class FlakySession:
        def __init__(self):
            self.calls = 0

        def get_kline(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("ErrCode: 10016 server restarting")
            return {"retCode": 0, "time": 20000, "result": {"list": []}}

    monkeypatch.setattr("hyro_bot.client.time.sleep", lambda _: None)
    client = object.__new__(DemoReadOnlyClient)
    client.session = FlakySession()
    result = client.candles_range("BTCUSDT", "5", 6000, 10000, page_limit=2)
    assert result["retCode"] == 0
    assert client.session.calls == 2
