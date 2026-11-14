# AlphaScope

An English, local-first multi-asset research dashboard for a 24-hour hackathon. Built around the question: **What is the market weather, and what evidence supports taking risk?**

## Run

Python 3.11 or newer is recommended. No Node server, API key, GitHub account or external frontend CDN is required.

```bash
cd "/Users/chenliangyu/Downloads/py bootacamp/alphascope"
python3 -m pip install -r requirements.txt
python3 server.py --port 8765
```

Open **http://127.0.0.1:8765**. The application binds to loopback only. `PORT=8766 python3 server.py` selects an alternative port. `.env.example` documents configuration; `.env` is not loaded automatically.

In the supplied environment, pandas/numpy/pytest are already installed. Cached real-source observations are included in the private ZIP backup; the first source refresh needs internet access. A failed refresh preserves the original retrieval timestamp and explicitly marks the cache as stale. No synthetic prices or fake news are generated.

## Product

- **Market Overview:** market weather, SPY, effective federal funds rate, matched-date 10Y–2Y spread, official Cboe VIX history, watchlist and 11-sector ETF heatmap.
- **Global Markets:** ten representative major-market indices: S&P 500, FTSE 100, Nikkei 225, Shanghai Composite, Hang Seng, DAX, CAC 40, Nifty 50, S&P/TSX Composite and S&P/ASX 200. Daily local-currency levels, moves, dates, exchange timezones and an exact-common-date normalized comparison. This is a geographically diverse watchlist, not a capitalization ranking.
- **Asset Explorer:** ticker search, adjusted history, 20/60-session averages, 63-session momentum, Wilder-style RSI and realized volatility. Source metadata stays with each series.
- **Strategy Lab:** five deterministic models, matched-period benchmark, costs, equity/drawdown curves, return statistics, position episodes and complete execution-fill export.
- **Storm Replay / Market Multiverse:** build a hypothetical portfolio, navigate source-backed historical storms, and compare your decisions with buy-and-hold and a fixed risk rule. The flagship creative demo includes a spacecraft, a drawdown-budget meter and a three-route debrief.
- **New Worlds:** user-controlled duration and normal-distribution VaR scenarios. These are clearly hypothetical educational models, not backtested trading strategies.
- **News & Context:** dated, linked official Federal Reserve releases.
- **Politics & Markets:** original BBC News US/Canada RSS headlines, political keyword annotations, FEC-sourced 2018/2022/2026 midterm dates, asset/sector event windows and VIX point changes. Incomplete future windows remain incomplete. This is descriptive analysis, not a causal election-effect estimate.
- **Transmission Map:** seven interactive nodes separate official event records, unestimated policy/valuation/earnings hypotheses, real historical ETF evidence, and editable exposure assumptions. Sources, counterevidence, partial windows and cross-page evidence links remain explicit.
- **Risk Radar:** explicit market/portfolio review alerts for source quality, VIX, realized volatility, observed session losses, trend, ETF concentration and replay drawdown budgets. Current and historical contexts stay separate; acknowledgment preserves severity. No continuous monitoring, push notification or automatic broker order.
- **Sources & Methods:** provider links, observation dates, retrieval timestamps, units, adjustment caveats, stale flags and SHA-256 fingerprints.

See [METHODOLOGY.md](METHODOLOGY.md) for exact timing, formulas and limitations and [DEMO.md](DEMO.md) for a three-minute walkthrough.

## Tests and reproduction

```bash
python3 -m pytest tests -q
python3 research.py
```

The second command runs the same fixed test-period rules across all 25 research assets and writes `reports/summary.json` plus full SPY, GLD and USO result files. It uses the exact cached source histories. To obtain a new dataset deliberately:

```bash
python3 research.py --refresh
```

Results after refresh may change because the dataset or provider adjustments change. Each report retains observation range, source hash and retrieval time. `requirements-lock.txt` records the versions used for delivery.

Optional browser QA is in `tools/browser_qa.cjs`; it needs an installed Node/Playwright runtime and a Chrome/Chromium executable. Set `PLAYWRIGHT_MODULE` to an absolute package path and `CHROME_PATH` to the browser binary if necessary. Run the local server first. Browser checks and screenshots are recorded in `reports/browser-qa.json` and `preview-*.png`.

## Data access and scope

- **Prices and ^IRX:** Yahoo Finance public chart endpoint, daily frequency. Personal research prototype; access is unofficial, can change or be rate-limited, and is not a commercial redistribution license. [Provider usage guidance](https://ranaroussi.github.io/yfinance/).
- **VIX:** [Cboe official historical data](https://www.cboe.com/tradable-products/vix/vix-historical-data), with the original CSV URL retained. Index levels are not investable total returns. No VIX-futures P&L is claimed.
- **FRED:** CSV retrieval was tested but timed out in this environment. The delivered DFF/DGS2/DGS10/DFII10 data are a small, separately labelled official-page snapshot verified on 2026-11-14. Original observation dates and retrieval timestamps are preserved. These observations provide current context only and never enter historical strategy signals.
- **Rate-aware strategy:** separate historical Yahoo **^IRX 13-week Treasury-bill yield proxy**, strictly lagged to an observation before the signal date, with a maximum seven-day carry. It is not the federal funds rate.
- **Policy news:** [Federal Reserve official RSS](https://www.federalreserve.gov/feeds/feeds.htm).
- **Political news:** [BBC News](https://www.bbc.com/news) original US/Canada RSS titles, dates and links for a personal non-commercial feed reader. No article bodies or images are copied. Political badges are our keyword annotations, not publisher judgments. Public/commercial redistribution requires review of publisher permissions.
- **Election dates:** FEC source links are stored per event. No election winner, political outcome or specific policy enactment is inferred from a date.

This is research and learning software. It does not connect to a broker. GLD/USO are explicitly labelled ETF proxies; they do not represent executable gold/oil futures returns. There are no corporate-fundamental valuation models or generated AI news summaries in this version.

## Files

`server.py` serves local JSON endpoints and static assets. `data_service.py` handles providers and cached provenance. `engine.py` implements indicators and the cash/units ledger. `politics.py` implements sourced news and descriptive event windows. `research.py` reproduces batch reports. `tests/` contains numeric, timing, provenance and event-window tests.

All Git history is local. There is no configured GitHub dependency or remote repository. The sibling `AlphaScope-backup.zip` is a private copy of code, source data, tests, reports, screenshots and local Git history.

## Market Multiverse / Storm Replay

Open **Storm Replay** for the interactive flagship demo. Launch a hypothetical $100,000 ETF portfolio into the 2020 volatility storm or 2022 rate-shift world. Adjust SPY/GLD/USO/TLT allocations, leave the remainder in cash, and set a user-defined drawdown budget.

Each decision reveals up to ten completed common sessions. A decision made after the displayed close executes no earlier than the next close. Compare your route with the same initial allocation held without rebalancing and a fixed, lagged risk rule. The portfolio spacecraft and drawdown meter are learning metaphors, not survival probabilities, margin estimates or guarantees.

The historical-news capsule stays locked until the selected Federal Reserve release was published. Current news and FRED snapshots are excluded. The replay API withholds future prices and wealth curves, but other research pages contain historical data, and participants may already know the scenario. This is an educational replay, not a blind or independent skill test.

Final debriefs show return, maximum drawdown, costs and execution fills. Export retains every revealed daily portfolio value, decision, fill, source and assumption. Sessions are in memory, limited to 32; restarting the server clears active games. Preserve your route by exporting before restarting.

Implementation: `replay.py`. Tests: `tests/test_replay.py`. Optional browser journey: `tools/replay_browser_qa.cjs`, with the same Playwright/Chrome environment variables as the main browser checks. Evidence: `reports/replay-browser-qa.json` and `reports/replay-browser-export.json`.

## Risk Radar

Open Risk Radar for current-market review flags, or inspect the separately labelled historical alerts inside Storm Replay. Each alert includes its observation date, measured value, trigger threshold, interpretation and source evidence. ETF target concentration can be checked using the allocation form. Edits are evaluated only when you press **Check these targets**; this is not a connected live portfolio.

Marking an alert reviewed retains its severity and trigger. Review state is stored only in the browser for that context/date/value. Alert evidence can be exported. The header summarizes loaded current-market flags; during replay it switches to **Historical mode** to avoid presenting current information as part of the historical decision.

The threshold register lists the exact fixed rules and their limitations. There are no automatic orders, stop-loss execution, push notifications or continuous surveillance. Checks run when data is loaded, an allocation is checked or the replay advances; source caching still applies. See `risk.py`, `tests/test_risk.py`, and `reports/risk-browser-qa.json` for implementation and verification.

## Transmission Map

Open **Transmission Map** to connect the research workflow: an official event record, conjectured policy/valuation/earnings/uncertainty channels, descriptive historical ETF windows, and editable portfolio assumptions. Cases include the 2026 and 2022 US midterms and the 16 March 2022 Fed rate announcement.

Seven clickable nodes use four explicit evidence types. Dashed arrows are **unestimated hypotheses**, not learned causal links. Each node includes a question, counterevidence and source/background context. Historical returns are adjusted-price changes before trading costs, not strategy P&L or event-attributable returns. The 2026 window remains partial when future sessions are unavailable.

The exposure form changes only user assumptions, never the observed market evidence. It does not estimate portfolio returns or look through ETF constituents. Links open the matching election/asset study, a separate fixed-strategy backtest, or a separately dated current Risk Radar allocation check. Export includes the graph, event sources, all fifteen asset/sector windows and the assumptions.

Implementation: `transmission.py`. Tests: `tests/test_transmission.py`. Browser verification: `tools/transmission_browser_qa.cjs`. No generated news claims, political winner inference, causal effect estimates or future return forecasts are supplied.
