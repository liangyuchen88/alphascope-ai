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

## Storm Replay: source-backed portfolio counterfactuals

The two fixed scenarios use common completed SPY/GLD/USO/TLT daily observations: 2020-02-19 to 2020-05-15, and 2022-03-15 to 2022-06-30. These are chosen historical windows, not randomly selected test samples. Initial capital is a clearly hypothetical USD 100,000. The selected allocation is long-only, total ETF weights at most 100%, remainder zero-yield cash. At least 63 common observations before launch warm up indicators. Cboe VIX is joined by exact date and is a risk indicator, never a portfolio holding.

The initial snapshot contains only prices up through the displayed close and starting cash. Each user decision executes at the next common close; the previous holdings earn the intervening close-to-close return. One decision advances at most ten observed sessions. “Keep holdings” does not rebalance; at the initial launch it queues the initial allocation for the first next close. A rebalance targets user weights against post-cost equity. All portfolios liquidate at the last common close and pay exit costs.

The buy-and-hold comparison buys the same initial allocation at the same first execution close and holds the units, without periodic rebalancing. The fixed risk comparison targets the initial ETF allocation times a scale based only on previous-session SPY values: `min(1, 0.12 / 20-return annualized volatility)`, multiplied by 1 above the 60-observation SMA or 0.25 below. It rebalances daily with the same costs. These are fixed educational coefficients, not fitted optimal allocations or a claim of superior performance across regimes.

Simultaneous multi-asset turnover and fees are solved against post-cost NAV. For marked pre-trade value V, current invested values A_j, target weights w_j, and one-way cost rate c, solve the monotone equation `N + c × sum(abs(w_j × N − A_j)) = V` by bisection. Set invested values to `w_j × N`, cash to `N × (1 − sum(w_j))` and charge each absolute trade its fee/slippage. Default c is 5 bps fees plus 5 bps slippage. Adjusted-unit accounting is a portfolio research approximation, not a broker fill simulator. No leverage, impact, taxes or futures rolling is included. Per-trade win rate is N/A for these multi-asset paths; every execution fill is separately retained.

The displayed drawdown budget is the user's threshold against the portfolio's realized maximum drawdown from its starting/peak wealth. Budget use can exceed 100%; the visual bar is capped at full width while the numeric ratio remains accurate. Breaching the threshold does not place an automatic stop or simulate margin liquidation.

The March 15, 2020 Fed release (5 p.m. EDT, a Sunday) is visible from the next revealed session after publication; the March 16, 2022 release (2 p.m. EDT) is available by that day's displayed close. Only brief paraphrases of these linked official sources are used. No current political or policy news is injected into past decisions. No causal attribution is made from a release to a subsequent price move.

Server snapshots are detached copies. Sequential turn numbers prevent double-clicks or stale requests from advancing a route twice. Invalid or overallocated targets are rejected before mutation. Future observations and wealth curves are withheld by the replay API, but other research endpoints contain history and scenario names identify familiar events. Thus replay outcomes are not independent, untouched, blind or predictive validation. Current-vintage adjusted histories may incorporate later corporate-action revisions. Exported evidence preserves this limitation.

## Risk Radar: transparent review alerts

Risk Radar evaluates explicit display rules, not a calibrated trading model. Thresholds are manual design assumptions and are not claimed to predict losses, optimize returns or provide statistical safety guarantees. The alert itself never changes portfolio weights or places an order.

| Check | Warning | Critical |
| --- | --- | --- |
| VIX | At least 20 index points | At least 30 |
| SPY 20-return annualized realized volatility | At least 25% | At least 35% |
| Latest SPY adjacent-observation loss | At least 2% | At least 3% |
| SPY trend | Close below its 60-session average | Not applicable |
| Largest ETF target or holding | More than 60% of portfolio | More than 80% |
| Replay realized maximum drawdown / user budget | At least 80% of budget | At least 100% |

Data age greater than five calendar days, future-dated observations, missing data or a failed refresh suppress current classification for the affected SPY/VIX source. Missing indicators and stale watchlist assets produce unavailable-data alerts. A missing value never becomes a zero-risk observation. Verified FRED snapshots retain an informational limitation note rather than being described as a live macro feed. No configured trigger means only that the covered thresholds did not trigger; it does not establish safety.

The allocation form checks **user-entered ETF targets**, not a connected live portfolio. ETF concentration is fund-level exposure and does not model issuer overlap, correlation, margin, liquidity, derivatives or portfolio VaR. Actual hypothetical holdings and realized drawdown are available separately in Storm Replay.

Historical replay alerts use only the revealed date, exact-date VIX, past SPY indicators, actual hypothetical holdings and realized drawdown. They never compare 2020 dates with today's calendar to label history stale, and they never inject current-market observations. The global current-market badge is hidden in historical play. Current-vintage source retrieval timestamps remain inspectable as provenance; they are not treated as historical news inputs.

Each alert retains its rule ID, severity, value, threshold, units, observation date, source links/hash where applicable, review guidance and `automatic_action: false`. Review acknowledgments are browser-local and keyed by context, rule, date, value and threshold. Marking reviewed does not clear the trigger or lower the severity; changed observations have a different review key. Export captures the risk context, covered inputs, thresholds and evidence.

Checks run on source load, allocation checks or replay turns. Caches normally refresh after six hours. This is not continuous surveillance, a push-notification service, stop-loss execution or a broker-connected risk control system. These limits are visible in the interface.

## Transmission Map: evidence types and unestimated channels

The map offers official event records for the 2026/2022 US midterm dates (FEC references) and the 16 March 2022 FOMC rate increase (official statement, 2 p.m. EDT, target range 0.25–0.50%). A record establishes only its stated fact; an election date does not establish a winner or enacted policy. Event reference links were checked on 2026-11-14.

Nodes have four mutually explicit labels: official record, hypothesis, historical observation, and user assumption. Every arrow is an unestimated proposed channel or exposure question. General Federal Reserve and ECB transmission explanations provide background, not evidence identifying a causal effect in a selected event. No directional probability, coefficient, price target or predicted P&L is generated.

For each event, the existing descriptive event-window method is applied separately to SPY, GLD, USO, TLT and eleven sector ETFs, with SPY and exact-date Cboe VIX as references. Baseline is the last common pre-event close; the endpoint is the requested +5/+20/+60 common sessions, or the latest available session if incomplete. Source fingerprints, observation dates, incomplete coverage and original metadata remain in the export. A policy release at 2 p.m. can share a session with pre-release moves; a close-to-close window cannot isolate its effect. Returns are before trading costs, not executable event strategies or causal alpha.

Missing series remain unavailable. Changing user-entered target weights never changes historical observations. SPY/GLD/USO/TLT weights describe broad exposures only; there is no issuer-level look-through or estimated event-specific sensitivity. Map links explicitly distinguish matching retrospective election evidence from Strategy Lab's separate evaluation periods and Risk Radar's current-date allocation checks.

The interface supplies alternative explanations and reversal conditions at every node. Inflation, earnings, growth, prior expectations, policy enactment, positioning and other events can invalidate a simple story. Price co-movement is a reason to investigate, not proof of the arrows. The map is not used as a historical trading signal, and current news never enters its retrospective strategy calculations.
