import pytest

from hyro_bot.config import Settings


def test_demo_is_required(monkeypatch):
    monkeypatch.setenv("BYBIT_DEMO", "false")
    with pytest.raises(ValueError, match="Only Bybit Demo"):
        Settings.from_env()


def test_order_enablement_is_rejected(monkeypatch):
    monkeypatch.setenv("BYBIT_DEMO", "true")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    with pytest.raises(ValueError, match="not implemented"):
        Settings.from_env()


def test_credentials_are_optional_for_public_data(monkeypatch):
    monkeypatch.setenv("BYBIT_DEMO", "true")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.delenv("BYBIT_API_KEY", raising=False)
    monkeypatch.delenv("BYBIT_API_SECRET", raising=False)
    assert not Settings.from_env().has_credentials


def test_symbol_list_accepts_usdt_pairs_and_rejects_non_usdt(monkeypatch):
    monkeypatch.setenv("BYBIT_DEMO", "true")
    monkeypatch.setenv("TRADING_ENABLED", "false")
    monkeypatch.setenv("TRADING_SYMBOLS", "SOLUSDT, XRPUSDT, SOLUSDT")
    assert Settings.from_env().symbols == ("SOLUSDT", "XRPUSDT")
    monkeypatch.setenv("TRADING_SYMBOLS", "BTCUSD")
    with pytest.raises(ValueError, match="BASEUSDT"):
        Settings.from_env()
