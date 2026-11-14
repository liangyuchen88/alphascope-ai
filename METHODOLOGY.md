# Research methodology

## Observation and provenance

Each market series stores provider, symbol, source/request URL, frequency, exchange timezone, currency or units, adjustment description, retrieval time, caveats and a hash of its observation rows. Every row has its own observation date and value. These daily observations are not exchange-certified real-time prices.

Yahoo equity/ETF histories use the provider's dividend/split-adjusted close when available; otherwise they explicitly show unadjusted prices. Only dates before the current date in the exchange timezone are used, conservatively excluding the current session. Corporate actions can revise historical adjusted values. Do not interpret adjusted units or prices as broker order fills.

Missing observations are omitted, never invented or interpolated. Returns use adjacent available observations; annualization assumes 252 sessions/year. Provider omissions can therefore affect estimates and deserve inspection. Calendar holidays and market closures differ by country. FRED spreads use the latest date shared by both series, rather than subtracting mismatched dates. Observations more than five calendar days old or an unsuccessful refresh are flagged stale. Caches refresh after six hours. FRED official-page snapshots retain a visible snapshot annotation even while recent.

## Indicators and five fixed models

- **SMA trend:** target weight 1 when 20-session SMA exceeds 60-session SMA, otherwise 0.
- **Momentum:** target weight 1 when adjusted close is above its level 63 sessions earlier, otherwise 0.
- **RSI mean reversion:** Wilder-style exponentially smoothed gains/losses (`alpha=1/14`, initial warm-up of 14 returns); enter below 30, exit above 55. A flat series has RSI 50; a rising series with zero losses has RSI 100. This pandas initialization is not an exact replication of every chart vendor's initialization.
- **Volatility target:** `min(1, 0.12 / realized_volatility)` when close exceeds its 60-session SMA; otherwise 0. Realized volatility is the 20-return sample standard deviation times sqrt(252). No leverage.
- **Rate-aware risk budget:** the volatility-target weight divided by `1 + 5 × max(short_yield, 0) / 100`. The short yield is historical Yahoo ^IRX, a 13-week Treasury-bill yield proxy in percent. An as-of join uses observations **strictly before** each signal date, maximum seven calendar days old. Missing yield means zero exposure; coverage below 95% in the evaluation period invalidates the backtest. Coefficient 5 is a fixed educational assumption, not a fitted optimum.

All models have at least 63 initial observations reserved for warm-up. No parameter search, optimization, expected-profit forecast or machine-learning model is used.

## Execution ledger

Signal `s[t]` uses data through close t. Its target is executed at close t+1. Its first price return is close t+1 to close t+2. Every evaluation period starts with cash and zero inherited position; earlier history may warm up indicators. The final session liquidates the portfolio rather than opening a new position.

The ledger tracks cash and fractional adjusted units. After the day's price change, it solves for target invested value **including transaction costs**. If target weight is w, pre-trade marked value V, existing invested value A and one-way rate c:

- Buy: new invested value = `w × (V + c × A) / (1 + w × c)`.
- Sell: new invested value = `w × (V − c × A) / (1 − w × c)`.
- Fee/slippage = `c × abs(new invested value − A)`.

This accounts for weight drift, fractional rebalances and the cash needed to pay fees. Defaults: 5 bps fee + 5 bps slippage per side. Idle cash earns zero. No borrowing, shorting, leverage, taxes, market impact or volume-based fill constraints. Final-close liquidation incurs cost. Every execution fill is retained with its signal date, side, target weight, normalized notional, cost and terminal-liquidation flag.

The buy-and-hold benchmark starts at the first evaluated close, pays entry costs, holds the same asset and exits at the same final close with exit costs. Strategy and benchmark use the same observed period. Trading episodes summarize binary-entry/exit positions. For models with fractional daily rebalances, per-episode win rates and per-trade returns are N/A; exports retain every fill.

## Evaluation split

Fixed calendar dates, not percentages that move when data are appended:

- Development: before 2023-01-01, after warm-up.
- Validation: calendar 2023.
- Reserved test: 2024-01-01 onward.
- All history: explicitly exploratory.

No parameters were optimized against any of these periods. Nevertheless this is a retrospective development exercise, and the developer has inspected test results. It is not an independently untouched preregistered trial. Repeated interactive use further compromises test independence. Survivorship bias remains in the hand-selected current stock/ETF universe. Current-vintage adjusted histories are not a point-in-time security master.

## Metrics

For n daily net returns r and wealth beginning at 1:

- Cumulative return: final wealth − 1.
- CAGR: final wealth^(252/n) − 1; N/A for fewer than 252 sessions.
- Annualized arithmetic return: mean(r) × 252; at least 20 sessions.
- Annualized volatility: sample stdev(r) × sqrt(252); at least 20 sessions.
- Sharpe: mean(r) × 252 / annualized volatility. Risk-free reference 0; at least 60 sessions and nonzero volatility.
- Sortino: mean(r) × 252 / (sqrt(mean(min(r,0)^2)) × sqrt(252)). MAR 0; at least 60 sessions and nonzero downside deviation.
- Drawdown: wealth / running peak − 1. Initial wealth of 1 is included in the peak.
- Maximum drawdown: minimum drawdown.
- Trade win rate: proportion of closed binary position episodes with net return above zero. Terminal liquidation is included. Fractional models show N/A.
- Turnover: sum of absolute execution notional divided by marked pre-cost NAV at each execution.
- Cost-fraction sum: sum of daily transaction cost / marked pre-cost NAV. This is not the compounded difference between a free and paid strategy.

N/A is returned for invalid or insufficient statistics, rather than an invented zero or infinity.

## Political news and election windows

BBC RSS titles are retained with original links, source names and publication dates. Keyword badges are transparent application annotations. There is no generated factual summary or winner prediction. Today's news is never used in past trading rules.

Election dates for 2018, 2022 and 2026 come from linked FEC calendars. Session 0 is the first common available asset/SPY session on or after the election date. Session -1 close is the common baseline. Curves show each adjusted price divided by that baseline, minus 1. Asset minus SPY is a descriptive return difference, not factor-model alpha. Checkpoints are +0, +1, +5, +20 or +60 completed sessions, as requested. An unfinished post-event window is labelled partial; no future values are filled.

Cboe VIX is joined by exact observation date. Differences are index points, not investment returns. Missing VIX observations remain missing and chart lines show gaps. We do not assume election results became known precisely at election-day close. Earnings, monetary decisions, inflation announcements, policy expectations and positioning can overlap the event. Three selected elections cannot establish causality, statistical significance or a profitable election strategy.

## Scenarios and VIX risk bands

The New Worlds duration lens uses `ΔP/P ≈ −modified duration × Δyield`. Duration and yield shocks are user inputs, not observed GLD/USO parameters. Convexity, coupons and spreads are omitted. The sizing lens is daily budget divided by `1.645 × annual volatility / sqrt(252)`. Normality, independence and stable volatility are strong educational assumptions, not loss guarantees.

VIX bands below 20, 20–30 and 30+ are explicit display heuristics, not Cboe trading recommendations or validated strategies. VIX is a 30-day option-implied volatility index, not directly investable. No VIX futures, oil futures or gold futures execution, roll, margin or contract P&L is modeled.


## Ten major-market indices

The fixed geographic watchlist covers the United States (S&P 500), United Kingdom (FTSE 100), Japan (Nikkei 225), mainland China (Shanghai Composite), Hong Kong (Hang Seng), Germany (DAX), France (CAC 40), India (Nifty 50), Canada (S&P/TSX Composite) and Australia (S&P/ASX 200). Selection is for geographic coverage, not a capitalization ranking or an exhaustive global universe.

Daily comparisons use exact common dates among available series and rebase the latest 126 common observations to 100 at the first date. Missing series are explicitly listed, excluded from the comparison and never replaced with fabricated observations. No forward-fill or FX conversion is performed. Local currencies, constituents, weighting and price/total-return methodologies differ; the commonly quoted DAX is a performance index. The same calendar date does not mean simultaneous closes. This is not a USD portfolio return or an investable index/futures backtest. Index levels are excluded from the strategy backtest endpoint.
