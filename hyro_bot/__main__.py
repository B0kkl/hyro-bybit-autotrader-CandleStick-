import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from .candles import completed_candles
from .client import DemoReadOnlyClient
from .config import Settings
from .signals import build_plan, load_manual_signal
from .strategy import analyze
from .backtest import run_backtest, run_portfolio_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Bybit Demo signal and analysis tool")
    parser.add_argument("--manual", action="store_true", help="validate a manual TP/SL signal file")
    parser.add_argument("--hybrid", action="store_true", help="preview an enabled manual signal and automatic analysis together")
    parser.add_argument("--backtest", action="store_true", help="walk-forward test the current automatic rules")
    parser.add_argument("--backtest-days", type=int, default=90, help="historical lookback days (1-180, default 90)")
    parser.add_argument("--slippage-bps", type=float, default=None, help="estimated adverse slippage per side; overrides .env")
    parser.add_argument("--max-open-positions", type=int, default=1)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--daily-loss-limit-usdt", type=float, default=250.0)
    parser.add_argument("--risk-pct", type=float, default=2.0,
                        help="simulated account risk per trade percentage (default 2; maximum 2)")
    args = parser.parse_args()
    load_dotenv()
    settings = Settings.from_env()
    client = DemoReadOnlyClient(settings)
    if not settings.has_credentials:
        raise SystemExit("Add Bybit Demo credentials to .env for account-aware signal sizing.")
    if not 1 <= args.backtest_days <= 180:
        raise SystemExit("--backtest-days must be between 1 and 180")
    slippage_bps = args.slippage_bps if args.slippage_bps is not None else settings.backtest_slippage_bps
    if slippage_bps is not None and slippage_bps < 0:
        raise SystemExit("--slippage-bps must be non-negative")
    if args.max_open_positions < 1 or args.max_trades_per_day < 1 or args.daily_loss_limit_usdt <= 0 or not 0 < args.risk_pct <= 2:
        raise SystemExit("Portfolio limits must be positive")
    if args.manual or args.hybrid:
        signal = load_manual_signal(
            Path(__file__).resolve().parent.parent / "signals" / "manual_signal.json",
            require_enabled=args.manual,
        )
        if signal.get("enabled") is not True:
            print("Manual signal disabled; continuing with automatic analysis only.")
            if args.manual:
                raise SystemExit("Set enabled to true to preview the manual signal.")
        else:
            if signal.get("symbol", "").upper() not in settings.symbols:
                raise SystemExit("Manual signal symbol must also be included in TRADING_SYMBOLS in .env")
            contract = client.instrument_info(signal["symbol"].upper())
            wallet = client.wallet_balance()
            if wallet.get("retCode") != 0:
                raise SystemExit("Could not read Demo wallet; manual signal was not processed.")
            equity = float(wallet["result"]["list"][0]["totalAvailableBalance"])
            plan = build_plan(signal, equity, allowed_symbols=set(settings.symbols))
            print("VALIDATED MANUAL SIGNAL — PREVIEW ONLY; NO ORDER SENT")
            print(json.dumps({
                "instrument_check": "PASS",
                "tickSize": contract.get("priceFilter", {}).get("tickSize"),
                "qtyStep": contract.get("lotSizeFilter", {}).get("qtyStep"),
                "minOrderQty": contract.get("lotSizeFilter", {}).get("minOrderQty"),
                "minNotionalValue": contract.get("lotSizeFilter", {}).get("minNotionalValue"),
            }, indent=2))
            print(json.dumps(plan.__dict__, indent=2))
        if args.manual:
            return
    backtest_reports = []
    for symbol in settings.symbols:
        contract = client.instrument_info(symbol)
        print(json.dumps({
            "instrument_check": "PASS",
            "symbol": symbol,
            "contractType": contract.get("contractType"),
            "status": contract.get("status"),
            "settleCoin": contract.get("settleCoin"),
            "tickSize": contract.get("priceFilter", {}).get("tickSize"),
            "qtyStep": contract.get("lotSizeFilter", {}).get("qtyStep"),
            "minOrderQty": contract.get("lotSizeFilter", {}).get("minOrderQty"),
            "minNotionalValue": contract.get("lotSizeFilter", {}).get("minNotionalValue"),
        }, indent=2))
        all_bars = {}
        for interval in ("240", "60", "15", "5"):
            if args.backtest:
                end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                start_ms = int((datetime.now(timezone.utc) - timedelta(days=args.backtest_days)).timestamp() * 1000)
                response = client.candles_range(symbol, interval, start_ms, end_ms)
            else:
                response = client.candles(symbol, interval, 100)
            all_bars[interval] = completed_candles(response, interval)
        if args.backtest:
            taker_fee_rate = None
            fee_warning = None
            try:
                fee_response = client.fee_rates(symbol)
                if fee_response.get("retCode") == 0:
                    fee_rows = fee_response.get("result", {}).get("list", [])
                    fee_row = next((row for row in fee_rows if row.get("symbol") == symbol), None)
                    if fee_row and fee_row.get("takerFeeRate") is not None:
                        taker_fee_rate = float(fee_row["takerFeeRate"])
                if taker_fee_rate is None:
                    fee_warning = "Demo API did not return this symbol's taker fee rate"
            except Exception:
                fee_warning = "Demo fee-rate endpoint unavailable; fee-adjusted result omitted"
            report = run_backtest(
                symbol, all_bars["240"], all_bars["60"], all_bars["15"], all_bars["5"],
                taker_fee_rate=taker_fee_rate,
                slippage_bps_per_side=slippage_bps,
            )
            report["fee_warning"] = fee_warning
            backtest_reports.append(report)
            print(json.dumps(report, indent=2))
            continue
        result = analyze(symbol, all_bars["240"], all_bars["60"], all_bars["15"], all_bars["5"])
        print(json.dumps(result.__dict__, indent=2))
    if args.backtest:
        wallet = client.wallet_balance()
        if wallet.get("retCode") != 0:
            raise SystemExit("Could not read Demo available balance for portfolio risk simulation")
        starting_balance = float(wallet["result"]["list"][0]["totalAvailableBalance"])
        portfolio = run_portfolio_backtest(
            backtest_reports, starting_balance,
            risk_pct=args.risk_pct,
            max_positions=args.max_open_positions,
            max_trades_per_day=args.max_trades_per_day,
            daily_loss_limit_usdt=args.daily_loss_limit_usdt,
        )
        print("ACCOUNT-LEVEL FILTERED BACKTEST (provisional limits)")
        print(json.dumps(portfolio, indent=2))
        return
    print("Analysis only: any signal is a preview; no order was sent.")


if __name__ == "__main__":
    main()
