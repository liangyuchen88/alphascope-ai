"""Ten representative global market indices; a geographic watchlist, not a ranking."""

import concurrent.futures
import pandas as pd
from data_service import prices, summary

MARKETS = [
    {"region": "United States", "index_symbol": "^GSPC", "index_label": "S&P 500"},
    {"region": "United Kingdom", "index_symbol": "^FTSE", "index_label": "FTSE 100"},
    {"region": "Japan", "index_symbol": "^N225", "index_label": "Nikkei 225"},
    {
        "region": "China",
        "index_symbol": "000001.SS",
        "index_label": "Shanghai Composite",
    },
    {"region": "Hong Kong", "index_symbol": "^HSI", "index_label": "Hang Seng"},
    {"region": "Germany", "index_symbol": "^GDAXI", "index_label": "DAX"},
    {"region": "France", "index_symbol": "^FCHI", "index_label": "CAC 40"},
    {"region": "India", "index_symbol": "^NSEI", "index_label": "Nifty 50"},
    {"region": "Canada", "index_symbol": "^GSPTSE", "index_label": "S&P/TSX Composite"},
    {"region": "Australia", "index_symbol": "^AXJO", "index_label": "S&P/ASX 200"},
]


def align_indices(histories, limit=126):
    """Exact shared dates; missing series remain absent, never forward-filled."""
    series = [
        pd.Series({r["date"]: r["close"] for r in rows}, name=symbol)
        for symbol, rows in histories.items()
        if rows
    ]
    if not series:
        return []
    aligned = pd.concat(series, axis=1).dropna().sort_index().tail(limit)
    if len(aligned) < 2:
        return []
    normalized = aligned.div(aligned.iloc[0]) * 100
    return [
        {"date": str(date), **{k: float(v) for k, v in row.items()}}
        for date, row in normalized.iterrows()
    ]


def world_view():
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        datasets = list(pool.map(prices, [m["index_symbol"] for m in MARKETS]))
    markets = [m | {"index": summary(d)} for m, d in zip(MARKETS, datasets)]
    histories = {
        m["index_symbol"]: d.get("rows", []) for m, d in zip(MARKETS, datasets)
    }
    return {
        "selection": {
            "name": "Ten major global market indices",
            "method": "A fixed, geographically diverse watchlist covering the US, UK, Japan, mainland China, Hong Kong, Germany, France, India, Canada and Australia. Selected representative indices, not a capitalization ranking or a claim of exhaustive global coverage.",
            "count": len(MARKETS),
        },
        "markets": markets,
        "comparison": align_indices(histories),
        "included_symbols": [s for s, rows in histories.items() if rows],
        "missing_symbols": [s for s, rows in histories.items() if not rows],
        "comparison_method": "Indices rebased to 100 on the first common date of the latest 126 common observations among available series. Missing series are explicitly listed and excluded; no invented values. Local-currency index changes, not USD investor returns. Constituents and price/total-return conventions differ (the commonly quoted DAX is a performance index). Exact shared dates only; no forward-fill. Same calendar date does not imply simultaneous closes. No executable index, futures or ETF P&L is claimed.",
    }
