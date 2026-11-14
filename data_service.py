import concurrent.futures, datetime as dt, hashlib, json, os, re, threading, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from engine import indicators

ROOT = Path(__file__).parent
CACHE = ROOT / "data"
CACHE.mkdir(exist_ok=True)
ASSETS = {
    "SPY": ("US large caps", "Index"),
    "QQQ": ("Nasdaq 100", "Index"),
    "AAPL": ("Apple", "Technology"),
    "MSFT": ("Microsoft", "Technology"),
    "NVDA": ("NVIDIA", "Semiconductors"),
    "AMZN": ("Amazon", "Consumer"),
    "GOOGL": ("Alphabet", "Communication"),
    "META": ("Meta", "Communication"),
    "TSLA": ("Tesla", "Consumer"),
    "JPM": ("JPMorgan", "Financials"),
    "XOM": ("Exxon Mobil", "Energy"),
    "GLD": ("Gold ETF · PROXY", "Commodity proxy"),
    "USO": ("Oil ETF · PROXY", "Commodity proxy"),
    "TLT": ("Long-duration Treasuries", "Bonds"),
    "XLK": ("Technology", "Sector"),
    "XLF": ("Financials", "Sector"),
    "XLE": ("Energy", "Sector"),
    "XLV": ("Healthcare", "Sector"),
    "XLI": ("Industrials", "Sector"),
    "XLY": ("Consumer discretionary", "Sector"),
    "XLP": ("Consumer staples", "Sector"),
    "XLU": ("Utilities", "Sector"),
    "XLRE": ("Real estate", "Sector"),
    "XLB": ("Materials", "Sector"),
    "XLC": ("Communication services", "Sector"),
}
lock = threading.RLock()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def download(url):
    with urllib.request.urlopen(
        urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 AlphaScope-Research/1.0"}
        ),
        timeout=12,
    ) as r:
        return r.read()


def cached(key, loader, refresh=False):
    path = CACHE / (key + ".json")
    with lock:
        old = json.loads(path.read_text()) if path.exists() else None
    if old and not refresh and time.time() - path.stat().st_mtime < 21600:
        return dict(old, cache_status="cached")
    try:
        value = loader()
        value["retrieved_at"] = now()
        with lock:
            path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return dict(value, cache_status="fresh")
    except Exception as e:
        if old:
            return dict(
                old,
                cache_status="stale",
                fetch_error=type(e).__name__ + ": " + str(e)[:160],
            )
        return {
            "error": type(e).__name__ + ": " + str(e)[:160],
            "status": "unavailable",
            "retrieved_at": None,
        }


def prices(symbol, refresh=False):
    if symbol == "^VIX":
        return vix(refresh)
    if symbol not in ("^IRX", "^VIX") and not re.fullmatch(
        r"\^?[A-Z0-9][A-Z0-9.\-]{0,14}", symbol
    ):
        raise ValueError("Invalid symbol")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=10y&interval=1d"

    def load():
        raw = json.loads(download(url))
        x = raw["chart"]["result"][0]
        q = x["indicators"]["quote"][0]
        adj = x["indicators"].get("adjclose", [{}])[0].get("adjclose")
        rows = []
        for i, t in enumerate(x["timestamp"]):
            # Only completed daily bars; timestamps are exchange-local calendar dates.
            zone = ZoneInfo(x["meta"].get("exchangeTimezoneName", "America/New_York"))
            date = dt.datetime.fromtimestamp(t, zone).date()
            if date >= dt.datetime.now(zone).date():
                continue
            c = (
                q["close"][i]
                if x["meta"].get("instrumentType") == "INDEX"
                else adj[i] if adj else q["close"][i]
            )
            if c is None or c <= 0:
                continue
            rows.append(
                {
                    "date": date.isoformat(),
                    "close": float(c),
                    "volume": q.get("volume", [None] * len(x["timestamp"]))[i],
                }
            )
        if len(rows) < 2:
            raise ValueError("No completed bars")
        return {
            "symbol": symbol,
            "name": ASSETS.get(symbol, (symbol, "Custom"))[0],
            "category": ASSETS.get(symbol, ("", "Custom"))[1],
            "rows": rows,
            "provider": "Yahoo Finance chart API",
            "url": f"https://finance.yahoo.com/quote/{symbol}/history/",
            "request_url": url,
            "frequency": "daily",
            "currency": x["meta"].get("currency", "USD"),
            "timezone": x["meta"].get("exchangeTimezoneName"),
            "instrument_type": x["meta"].get("instrumentType"),
            "exchange": x["meta"].get("exchangeName"),
            "adjustment": (
                "Provider-adjusted close (dividends/splits)"
                if adj
                else "Unadjusted close; not total return"
            ),
            "caveat": "May be delayed or revised. Personal research only; not exchange real-time quotes. GLD/USO are ETFs, not futures P&L.",
            "sha256": hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()
            ).hexdigest(),
        }

    result = cached("price_" + symbol, load, refresh)
    if result.get("instrument_type") == "INDEX":
        result.update(
            units="index points",
            adjustment="Published index level; index methodology may be price or total return",
            caveat="Representative index, not an investable asset. Local-currency methodology, constituents and closing times differ. Public provider history may be delayed or revised.",
        )
    if symbol == "^IRX":
        result.update(
            name="13-week US Treasury-bill yield proxy",
            units="percent per annum",
            currency=None,
            adjustment="Yield-index quote; not an investable price or return",
            caveat="Yahoo ^IRX short-yield proxy, not FRED DFF. Only pre-signal observations, maximum seven-day carry. May be revised or delayed.",
        )
    if symbol == "^VIX":
        result.update(
            name="Cboe Volatility Index",
            units="index points",
            currency=None,
            adjustment="Unadjusted volatility index level; not a total-return asset",
            caveat="Yahoo distribution of Cboe VIX. Expected 30-day S&P 500 volatility; not directly investable. Not VIX futures or an ETF return.",
        )
    return result


def summary(data):
    if "rows" not in data:
        return data
    rows = data["rows"]
    p = [r["close"] for r in rows]
    x = indicators(p).iloc[-1]

    def number(v):
        return None if pd.isna(v) else float(v)

    age = (
        dt.datetime.now(dt.timezone.utc).date()
        - dt.date.fromisoformat(rows[-1]["date"])
    ).days
    return {k: v for k, v in data.items() if k != "rows"} | {
        "last": p[-1],
        "date": rows[-1]["date"],
        "change": p[-1] / p[-2] - 1,
        "month_return": p[-1] / p[-22] - 1 if len(p) > 21 else None,
        "rsi": number(x.rsi),
        "volatility": number(x.volatility),
        "sma20": number(x.sma20),
        "sma60": number(x.sma60),
        "momentum": number(x.momentum),
        "stale": age > 5 or data.get("cache_status") == "stale",
        "age_days": age,
        "spark": [r["close"] for r in rows[-40:]],
    }


def macro(refresh=False):
    series = ["DFF", "DGS2", "DGS10", "DFII10"]

    def one(s):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}&cosd=2020-01-01"

        def load():
            import io

            frame = pd.read_csv(io.BytesIO(download(url)))
            frame.columns = ["date", "value"]
            frame.value = pd.to_numeric(frame.value, errors="coerce")
            frame = frame.dropna()
            if frame.empty:
                raise ValueError("Empty FRED series")
            return {
                "series": s,
                "provider": "FRED / Federal Reserve H.15",
                "url": f"https://fred.stlouisfed.org/series/{s}",
                "frequency": "daily",
                "units": "percent",
                "rows": frame.to_dict("records"),
                "caveat": "Observation dates are not publication timestamps. Latest revised version; not used as historical trading signals.",
            }

        return s, cached("macro_" + s, load, refresh)

    return dict(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(one, series))


def news(refresh=False):
    url = "https://www.federalreserve.gov/feeds/press_monetary.xml"

    def load():
        root = ET.fromstring(download(url))
        items = []
        for e in root.findall(".//item")[:15]:
            link = e.findtext("link", "")
            if not link.startswith("https://www.federalreserve.gov/"):
                continue
            items.append(
                {
                    "title": e.findtext("title", ""),
                    "url": link,
                    "published": e.findtext("pubDate", ""),
                    "source": "Federal Reserve",
                    "scope": "Monetary policy / Rates",
                    "interpretation": "Official policy release. Read the original document. Not used in historical backtest signals.",
                }
            )
        if not items:
            raise ValueError("No RSS entries")
        return {
            "provider": "Federal Reserve official RSS",
            "url": url,
            "items": items,
            "caveat": "Official policy releases only; not comprehensive company or commodity coverage. No generative AI factual summaries.",
        }

    return cached("news", load, refresh)


def overview():
    def one(s):
        return summary(prices(s)) | {
            "symbol": s,
            "name": ASSETS[s][0],
            "category": ASSETS[s][1],
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        assets = list(pool.map(one, ASSETS))
    rate_data = prices("^IRX")
    rate_source = {k: v for k, v in rate_data.items() if k != "rows"}
    rate_source["last_observation"] = rate_data.get("rows", [None])[-1]
    from politics import political_news

    vix_data = vix()
    result = {
        "assets": assets,
        "vix": vix_data,
        "political_news": political_news(),
        "rate_proxy": rate_source,
        "macro": macro(),
        "news": news(),
        "generated_at": now(),
        "mode": "REAL DATA / Authentic sources; missing data is never fabricated",
    }
    from risk import evaluate_market_risk

    result["risk"] = evaluate_market_risk(result)
    return result


def vix(refresh=False):
    url = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"

    def load():
        import io

        frame = pd.read_csv(io.BytesIO(download(url)))
        frame["date"] = pd.to_datetime(frame["DATE"], format="%m/%d/%Y").dt.strftime(
            "%Y-%m-%d"
        )
        rows = [
            {"date": r["date"], "close": float(r["CLOSE"]), "volume": None}
            for r in frame.to_dict("records")
            if pd.notna(r["CLOSE"]) and r["CLOSE"] > 0
        ]
        if not rows:
            raise ValueError("No official VIX observations")
        return {
            "symbol": "^VIX",
            "name": "Cboe Volatility Index",
            "category": "Risk indicator",
            "provider": "Cboe Global Markets (official historical CSV)",
            "url": "https://www.cboe.com/tradable-products/vix/vix-historical-data",
            "request_url": url,
            "frequency": "daily",
            "timezone": "America/Chicago",
            "currency": None,
            "units": "index points",
            "adjustment": "Unadjusted published VIX daily close",
            "rows": rows,
            "caveat": "Expected 30-day S&P 500 volatility implied by options. Not directly investable; not VIX futures, a volatility ETF or a return series. End-of-day history may be delayed or revised.",
            "sha256": hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()
            ).hexdigest(),
        }

    return cached("price_^VIX", load, refresh)
