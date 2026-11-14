# Three-minute flagship demo / Market Multiverse

**0:00–0:20 — Hook:** “If you could navigate a market storm again, would you make the same decisions? This spacecraft carries a hypothetical $100,000, but the market history is real.” Open Storm Replay and show the two worlds.

**0:20–0:45 — Build:** Select the 2020 world and adjust stock/gold/oil/Treasury ETF weights. Show unallocated cash and the drawdown budget. Launch. Point to the observed date and locked historical-news capsule. The first purchase has not happened yet: it executes at the next close.

**0:45–1:30 — Play:** Ask a judge whether to keep holdings or choose different targets. Reveal ten sessions. Ask again. Show the cost of a rebalance, changed portfolio wealth and the historical-news capsule appearing only after publication. Point to the historically dated Risk Radar warning: it explains the VIX trigger or drawdown-budget breach without placing an automatic order. The spacecraft is visual storytelling; the numbers come from historical prices.

**1:30–2:10 — Meet the other selves:** Advance the remaining chapters (seven turns in the 2020 window). Show the three-path debrief: the user's route, initial allocation held, and fixed risk rule. Compare return, drawdown, opportunity cost and execution costs. A familiar historical scenario cannot establish trading skill.

**2:10–2:40 — Show the evidence:** Export the route, show source fingerprints and next-close decision/fill dates. Open Transmission Map and select a hypothesis node: show the official event record, reversal conditions and real sector observations. Explain that arrows are unestimated mechanisms, not causal proof. Politics & Markets, Strategy Lab and Risk Radar are linked as separate evidence checks.

**2:40–3:00 — Close:** “We connect the creative New Worlds theme to an honest risk-learning loop: observe, decide, reveal and compare. This is not an unexplained buy button. It is a way to understand what risk feels like before taking it.”

Optional extension: open Forecast Lab, show the no-change benchmark and uncertainty band, and explain that lower forecast error is different from tradable profit. FX & Arbitrage separately checks actual fiat bid/ask loops; no positive result is fabricated when fees or depth erase it.

The longer research walkthrough follows below.

# Research dashboard walkthrough

## 0:00–0:30 — The problem

“During a market storm, traders do not need another unexplained buy button. They need to see the weather, inspect the evidence, and know when to wait. AlphaScope turns market data into an understandable research workflow.”

Open Market Overview. Point to market weather, SPY, FRED context and VIX. Explain that each observation has a date and a source. The rate snapshot is visibly labelled; it is not presented as a live feed.

## 0:30–0:55 — A global perspective

Open Global Markets. Show ten major-market indices, including the S&P 500, FTSE 100, Nikkei 225, Shanghai Composite and Hang Seng. Show each index's dated daily close and currency basis. Explain that this is a representative geographic watchlist, not a ranking. Rebase the indices to 100 to compare local-currency changes; these are not USD portfolio returns.

## 0:55–1:30 — Test a rule, do not trust a slogan

Open Asset Explorer and search SPY or AAPL. Show the trend, momentum, volatility and source evidence. Open Strategy Lab; choose Trend 20/60 and run it with the default fees/slippage. Point to the equity curve, buy-and-hold benchmark and maximum drawdown. Switch to the rate-aware rule to show that the model can reduce risk as observed short yields rise. Explain the strict historical lag and that the rule is fixed, not optimized.

“Signals formed at today's close execute no earlier than the next close. Both sides pay costs. Every rebalance is recorded, and you can export the exact data hash and assumptions.”

## 1:30–2:10 — Politics without hindsight

Open Politics & Markets. Show the dated BBC News links and the difference between publisher facts and our transmission hypotheses. Select 2022 midterms and a sector such as XLK. Show the event-day marker, comparison against SPY, sector table and VIX point changes.

“An election window can show what happened; it cannot by itself prove why. Earnings, inflation and central-bank decisions are competing explanations.”

Switch to 2026 and show the partial-window label: the app does not invent future observations. This is an event study, not a profitable-election-strategy claim.

## 2:10–2:40 — New Worlds

Open New Worlds. Move the yield shock from +50 bps to -100 bps with duration 7. Show the hypothetical +7% first-order bond-price sensitivity. Change the risk budget and show the model position size. Emphasize that inputs and outputs are labelled assumptions; they are not measured gold/oil sensitivities or guaranteed loss limits.

## 2:40–3:00 — Evidence and close

Open Sources & Methods or export a backtest. Show provenance, fees and the separation of development/validation/reserved-test periods.

“AlphaScope makes the decision process visible: observe the market, question the signal, test the rule, and understand the risk. Sometimes the most useful output is No Trade.”

## Judge questions

- **How do you prevent look-ahead?** Historical price signals execute next close. Rate proxies use only earlier observation dates, maximum seven-day carry. Current news and FRED snapshots are excluded from historical rules. Prefix-invariance and exact timing are tested.
- **Does it forecast prices?** Forecast Lab fits an inspectable ridge-regression model and tests it against no change. Most evaluated cases did not beat that benchmark. The separate strategy/replay rules are fixed and explainable; no LLM-generated price targets or factual news are used.
- **What is new?** A market-weather workflow joining global markets, political event windows, VIX, explainable models and hypothesis-controlled “New Worlds” scenarios, with an evidence panel instead of an unexplained trade command.
- **Can it trade futures?** The current release explicitly uses GLD/USO ETF proxies. Executable futures need contract specifications, rolls, margin and realistic execution; those are not claimed.
- **Is the election analysis causal?** No. It is descriptive, lacks a controlled causal design and uses too few selected events to validate a robust trading rule.
- **Can it work offline?** Included real-source caches allow private demo use. Missing sources are never fabricated; stale history is labelled. New refreshes need internet.
