"""WFE reported-exchange ranking, separate from daily local-currency index proxies."""

import concurrent.futures, hashlib, io, json, re
import pandas as pd
from data_service import cached, download, prices, summary

WFE_URL = "https://focus.world-exchanges.org/issue/november-2026/market-statistics"
PROXIES = {
    "Nasdaq - US": ("United States", "^IXIC", "Nasdaq Composite"),
    "NYSE": ("United States", "^NYA", "NYSE Composite"),
    "Shanghai Stock Exchange": ("China", "000001.SS", "Shanghai Composite"),
    "Japan Exchange Group": ("Japan", "^N225", "Nikkei 225 (selected-company proxy)"),
    "Euronext": ("Pan-European", "^N100", "Euronext 100 (selected-company proxy)"),
    "Shenzhen Stock Exchange": ("China", "399001.SZ", "Shenzhen Component"),
    "Hong Kong Exchanges and Clearing": (
        "Hong Kong",
        "^HSI",
        "Hang Seng (selected-company proxy)",
    ),
    "TMX Group": ("Canada", "^GSPTSE", "S&P/TSX Composite (Toronto proxy)"),
    "BSE India Limited": ("India", "^BSESN", "S&P BSE Sensex (selected-company proxy)"),
    "National Stock Exchange of India": (
        "India",
        "^NSEI",
        "Nifty 50 (selected-company proxy)",
    ),
    "Taiwan Stock Exchange": ("Taiwan", "^TWII", "Taiwan Weighted"),
    "Korea Exchange": ("South Korea", "^KS11", "KOSPI"),
    "Deutsche Boerse AG": ("Germany", "^GDAXI", "DAX (performance-index proxy)"),
    "SIX Swiss Exchange": ("Switzerland", "^SSMI", "Swiss Market Index"),
    "Saudi Exchange (Tadawul)": ("Saudi Arabia", "^TASI.SR", "Tadawul All Share"),
}


def rank_frame(frame):
    month_cols = [
        c for c in frame.columns if re.fullmatch(r"[A-Za-z]{3,4}'\d{2}", str(c))
    ]
    if not month_cols:
        raise ValueError("WFE table has no recognized monthly observations")

    def date(c):
        return pd.to_datetime(str(c).replace("Sept", "Sep"), format="%b'%y")

    column = max(month_cols, key=date)
    observation = (date(column) + pd.offsets.MonthEnd()).strftime("%Y-%m-%d")
    if "Exchange Name" not in frame.columns:
        raise ValueError("WFE exchange-name column unavailable")
    f = frame.copy()
    f["value"] = pd.to_numeric(
        f[column].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    eligible = f[
        f["value"].gt(0)
        & ~f["Exchange Name"].astype(str).str.contains("total", case=False, na=False)
    ].sort_values("value", ascending=False)
    rows = [
        {
            "rank": i + 1,
            "exchange": str(r["Exchange Name"]),
            "domestic_market_cap_usd_millions": float(r["value"]),
            "observation_date": observation,
        }
        for i, r in enumerate(eligible.head(10).to_dict("records"))
    ]
    if len(rows) < 10:
        raise ValueError("Fewer than ten valid reported exchange capitalizations")
    return {
        "column": str(column),
        "observation_date": observation,
        "reporting_exchanges": len(eligible),
        "rows": rows,
    }


def ranking(refresh=False):
    def load():
        raw = download(WFE_URL)
        frame = pd.read_html(io.BytesIO(raw))[0]
        result = rank_frame(frame)
        result.update(
            provider="World Federation of Exchanges / Focus",
            url=WFE_URL,
            publication="November 2026 issue",
            frequency="monthly",
            units="USD millions",
            adjustment="Domestic market capitalization as reported by WFE; USD conversion, subject to revision",
            caveat="Top ten among exchanges reporting the latest month in this publication, not a live ranking or a country ranking. Exchange groups and dual-listed issuers overlap; do not sum as a unique global universe. Representative indices are narrower proxies and have different methodologies.",
            sha256=hashlib.sha256(
                json.dumps(result["rows"], sort_keys=True).encode()
            ).hexdigest(),
        )
        return result

    return cached("global_ranking", load, refresh)


def world_view():
    rank = ranking()
    if "rows" not in rank:
        return {"ranking": rank, "markets": []}

    def one(r):
        country, symbol, label = PROXIES.get(
            r["exchange"], ("Not mapped", None, "No verified index mapping")
        )
        d = summary(prices(symbol)) if symbol else {"status": "unavailable"}
        return r | {
            "region": country,
            "index_symbol": symbol,
            "index_label": label,
            "index": d,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        markets = list(pool.map(one, rank["rows"]))
    # Rebase all indices on common dates. No FX conversion or forward-fill between timezones.
    histories = {
        m["index_symbol"]: prices(m["index_symbol"]).get("rows", [])
        for m in markets
        if m["index_symbol"]
    }
    series = []
    for symbol, rows in histories.items():
        if rows:
            series.append(pd.Series({r["date"]: r["close"] for r in rows}, name=symbol))
    comparison = []
    if series:
        aligned = pd.concat(series, axis=1).dropna().tail(126)
        if len(aligned) >= 2:
            normalized = aligned.div(aligned.iloc[0]) * 100
            comparison = [
                {"date": str(date), **{k: float(v) for k, v in row.items()}}
                for date, row in normalized.iterrows()
            ]
    return {
        "ranking": rank,
        "markets": markets,
        "comparison": comparison,
        "comparison_method": "Indices rebased to 100 on the first common date of the latest 126 common observations. Local-currency index changes, not USD investor returns; currencies, constituents and price/total-return conventions differ. Exact shared dates only; no forward-fill. Same calendar date does not imply simultaneous closes. No index-futures/ETF P&L is claimed.",
    }
