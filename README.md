# Hyro Candlestick Bot

Safe, signal-only starter for a Bybit Demo account used with a HyroTrader trial. It performs public candle downloads, private read-only account checks, multi-timeframe analysis, and manual signal validation. **Order execution is deliberately absent.**

## Integration facts

- HyroTrader says traders may create their own API key on their Bybit Demo account and use it with their own bot. A Hyro-created terminal key is not presumed to be portable; use the key from the same Bybit Demo account that HyroTrader tracks.
- Bybit Demo is a separate account and uses `https://api-demo.bybit.com`; its key/secret are distinct from mainnet and testnet.
- HyroTrader's setup guide asks for read/write, Unified Account, Assets enabled, and no IP restrictions for its connection. This bot's first check only calls read-only endpoints. Do not change or reuse the key linked to your challenge without confirming Hyro's rules for your setup.
- This project has no order placement code. Live endpoints are prohibited by the application configuration.

## Windows setup

Open this folder in Codex. In PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and add the Bybit Demo API credentials if you have a separate bot key. Never send them in chat or commit `.env`. If Windows blocks script activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that PowerShell window only, then activate again.

## Signal preview

```powershell
python -m pytest
python -m hyro_bot
```

Set the symbols in `.env` with a comma-separated `TRADING_SYMBOLS` value, for example `TRADING_SYMBOLS=SOLUSDT,XRPUSDT`. The starter list is `BTCUSDT,ETHUSDT`; at most 10 symbols can be configured at once. The bot checks that each is currently trading as a USDT-settled linear perpetual on Bybit Demo, then reports its current tick size and quantity constraints. Confirm each coin is also allowed in your specific HyroTrader challenge. This checks Bybit eligibility only; it does not query HyroTrader's account rules.

Run `python -m hyro_bot` to analyse completed 4H, 1H, 15M and 5M candles for the configured symbols. The initial rules are intentionally simple: 4H and 1H close breakout direction, a 15M bullish or bearish engulfing candle, then a 5M close beyond that setup candle. An aligned result is a **signal preview**, never an order. Results may be `NO_SIGNAL` often; this is expected.

For a manual preview, edit `signals/manual_signal.json`, set `enabled` to `true`, then provide `symbol`, `side` (`BUY` or `SELL`), `entry`, `stop_loss`, and `take_profit`. Run `python -m hyro_bot --manual`. The validator requires correctly ordered prices, at least 2:1 reward-to-risk, and risks no more than 2% of the current Bybit available balance. It reports a preliminary size estimate; instrument quantity steps, fees, funding, and slippage are not yet applied, so it is not an executable order size. Set `enabled` back to `false` when finished.

Run `python -m hyro_bot --hybrid` to preview an enabled manual signal **and** the automatic analysis in one pass. If the manual signal is disabled, the command reports that and continues with automatic analysis. This is not a continuous service and does not place either trade.

Run `python -m hyro_bot --backtest` to walk forward over 90 days of 4H/1H/15M/5M candles for configured symbols. Use `--backtest-days 30` to shorten the window (maximum 180 days). The bot attempts a read-only per-symbol taker fee lookup on the Demo API; if unavailable, fee-adjusted results are omitted. Set `BACKTEST_SLIPPAGE_BPS` in `.env` or pass `--slippage-bps` to model adverse slippage per side. Funding is not yet included. The account-level filter defaults to a fixed 2% of initial balance per trade (pass `--risk-pct 0.25` to compare the previous setting), one open position, three entries per UTC day, and a $250 realized daily loss cap unless overridden with `--daily-loss-limit-usdt`. It avoids a new entry when a full planned loss could breach the daily cap. Intraday unrealized drawdown, changing balance sizing, fees when unavailable, and funding are not modeled in that filter. Historical klines are retrieved in pages. If a 5M bar touches both barriers, the stop is assumed to hit first. Treat all results as exploratory rather than evidence of future profitability.

## Strategy and execution milestones

Before any execution is considered, expand historical backtesting with fees/slippage and validate outcomes, then test a demo order lifecycle with attached protective exits and failure recovery. The current signal size is only an estimate. Keep execution disabled until strategy, risk, backtest, and integration checks pass. Any later execution work must enforce the demo host in code, require explicit local opt-in, set protective exits, and fail closed on unknown account state.

## Current challenge details to confirm locally

The earlier plan suggested 5,000 USDT simulated balance. The current trial-risk preview defaults to 2% per trade; the user's dashboard showed a $250 daily drawdown and $500 max loss. This starter does not trade.
# hyro-bybit-autotrader-CandleStick-
