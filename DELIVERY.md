# Delivery verification

Verified on 2026-11-14T19:31:33.879469+00:00.

- English interface: thirteen pages, checked for untranslated Chinese UI on mobile.
- Unit/calculation/provenance/event-window tests: **87 passed**. Raw output: `reports/pytest-result.txt`.
- Isolated Chrome browser checks: **49 passed**, no JavaScript page errors. Full list: `reports/browser-qa.json`.
- Fixed historical research runs: **125/125 completed** across 25 assets and five models. Exact metrics and source fingerprints: `reports/summary.json`.
- HTTP smoke checks: six passed, including non-investable index rejection, malformed-symbol rejection and missing-file behavior. Evidence: `reports/http-smoke.json`.
- Storm Replay browser checks: **24 passed**, including hidden future observations, next-close execution, duplicate-turn rejection, all-cash rebalance, publication timing, mobile layouts, complete debrief and evidence export. See `reports/replay-browser-qa.json`. Together with the research suite, Risk Radar, Transmission Map and FX/forecast checks, 137 browser checks passed.
- Two genuine-history replay examples completed: 2020 storm (7 turns) and 2022 rate-shift (8 turns). Reports: `reports/replay-2020-storm-hold.json` and `reports/replay-2022-rates-hold.json`. These are hypothetical portfolios through known history, not blind skill validation.
- Risk Radar: **19 browser checks passed**, with 14 dedicated unit tests included in the 87-test total. Verified current/historical separation, no classification from stale VIX, ETF target concentration, drawdown alerts, retained reviewed state, export and mobile layouts. See `reports/risk-browser-qa.json`, `reports/risk-market.json` and `reports/risk-browser-export.json`. Thresholds are explicit display heuristics; no continuous monitoring or automatic orders are claimed.
- Transmission Map: **22 browser checks passed**, with 10 dedicated unit tests included in the 87-test total. Verified seven evidence-typed nodes, keyboard selection, primary-source links, counterevidence, partial windows, all fifteen price-evidence series, exposure edits, matching event/ticker links, separate current-risk context, export and mobile layout. See `reports/transmission-browser-qa.json`, `reports/transmission-browser-export.json` and `reports/transmission-*.json`. All arrows are unestimated hypotheses; no causal effect or portfolio forecast is claimed.
- FX/Forecast Lab: **23 browser checks passed** and 12 dedicated unit tests (included in 87 total). Verified genuine ECB references, fiat bid/ask orientation, all-leg costs, quote timing/capacity, source audits, FX-to-forecast links, both forecast horizons, FX/stock output, label/calibration timing and populated mobile layouts. See `reports/fx-forecast-browser-qa.json`, `reports/fx-reference.json`, `reports/fx-arbitrage-browser-export.json` and `reports/forecast-browser-export.json`. Public quotes remain execution-unverified.
- Forecast evaluations: **32/32 completed** across eight FX pairs plus eight stocks/ETFs at 1/5-observation horizons. Most did not beat the no-change RMSE baseline; no reliable trading advantage is established. See `reports/forecast-summary.json` and source-tagged full forecast examples. Statistical forecast evaluation is not a tradable P&L backtest.
- Actual browser download verified: `reports/browser-export-rate-aware.json`, including strict rate-date alignment and source provenance.
- Global markets: ten major-market indices covering the US, UK, Japan, mainland China, Hong Kong, Germany, France, India, Canada and Australia. All ten genuine histories retrieved; 126 exact-common-date observations available for normalized comparison. This is a geographic watchlist, not an exchange-capitalization ranking. Source/export: `reports/global-markets.json`.
- Elections: 2018 and 2022 completed +20-session windows; 2026 has only +8 completed post-event sessions as of the delivered 2026-11-13 observations and is explicitly partial. Source-tagged examples: `reports/event-*.json`.
- VIX: official Cboe daily history, with 9,316 observations in the delivery cache. Not an investable-return backtest.
- News: 15 official Federal Reserve releases and 23 BBC US/Canada RSS headlines in the delivered cache. Feed contents change over time.
- Screenshots: `preview-desktop.png`, `preview-mobile.png`, `preview-backtest.png`, `preview-politics.png`, `preview-global.png`, plus `preview-replay*.png` and `preview-risk*.png`, plus `preview-transmission*.png`, `preview-fx.png` and `preview-forecast*.png`.

## Material limits

FRED direct CSV/page requests timed out; the displayed macro observations are verified official-page snapshots with preserved dates and visible labels. The separate rate-aware strategy uses historical ^IRX instead. Historical adjusted data are current-vintage and may be revised. The development team inspected retrospective reserved-test results; this is not an independent preregistered trial. Political event analysis is descriptive, not causal. Gold/oil are ETF proxies, not executable futures models. News is not fed into historical strategy signals. No live broker connection, generated factual AI news, or fundamental valuation model is claimed.

FX reference rates are not executable transaction quotes. The fiat scanner reads independent REST order books and applies cost/timing/depth screens, but cannot verify actual account execution or guaranteed arbitrage. Forecast intervals are historical-residual estimates, not calibrated future guarantees; most tested cases did not beat the no-change benchmark. Current news and political outcomes are not numerical forecast inputs without point-in-time archives.

## Start and preserve

Run `python3 server.py --port 8765`, then open http://127.0.0.1:8765. Read `README.md` for dependency setup and reproduction. All Git milestones are local, without a remote. A sibling ZIP backup contains the complete project and real-source caches for private demo use.
