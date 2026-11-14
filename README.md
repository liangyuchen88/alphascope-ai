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
- **Global Markets:** top ten WFE reporting exchanges by domestic market capitalization, explicitly dated monthly ranking, local-currency index observations with exchange timezones, and exact-common-date normalized comparisons. Index proxies do not equal full exchange coverage.
- **Asset Explorer:** ticker search, adjusted history, 20/60-session averages, 63-session momentum, Wilder-style RSI and realized volatility. Source metadata stays with each series.
- **Strategy Lab:** five deterministic models, matched-period benchmark, costs, equity/drawdown curves, return statistics, position episodes and complete execution-fill export.
- **New Worlds:** user-controlled duration and normal-distribution VaR scenarios. These are clearly hypothetical educational models, not backtested trading strategies.
- **News & Context:** dated, linked official Federal Reserve releases.
- **Politics & Markets:** original BBC News US/Canada RSS headlines, political keyword annotations, FEC-sourced 2018/2022/2026 midterm dates, asset/sector event windows and VIX point changes. Incomplete future windows remain incomplete. This is descriptive analysis, not a causal election-effect estimate.
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
- **Exchange ranking:** [WFE Focus, November 2026 issue](https://focus.world-exchanges.org/issue/november-2026/market-statistics), latest observed column September 2026. This is a monthly ranking among reporting exchanges, not a live ranking or a country ranking. Dual listings and exchange groups can overlap.
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
