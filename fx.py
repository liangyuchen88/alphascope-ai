"""ECB reference FX data and conservative fiat-only triangular quote screening."""

import concurrent.futures, datetime as dt, hashlib, json, math, time, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from data_service import cached, download, now

CURRENCIES = ("EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "CNY", "HKD")
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
ECB_HOME = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
PAIRS = (
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "USD/CAD",
    "USD/CNY",
    "EUR/GBP",
)


def parse_ecb(raw):
    rows = []
    for e in ET.fromstring(raw).iter():
        date = e.attrib.get("time")
        if not date or date < "2016-01-01":
            continue
        rates = {"EUR": 1.0}
        for c in e:
            code = c.attrib.get("currency")
            v = c.attrib.get("rate")
            if code in CURRENCIES and v is not None:
                value = float(v)
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("Invalid ECB rate")
                rates[code] = value
        if len(rates) > 1:
            rows.append({"date": date, "rates": rates})
    rows.sort(key=lambda r: r["date"])
    if not rows or len({r["date"] for r in rows}) != len(rows):
        raise ValueError("ECB history missing or duplicated")
    return rows


def reference_history(refresh=False):
    def load():
        rows = parse_ecb(download(ECB_URL))
        return {
            "provider": "European Central Bank",
            "url": ECB_HOME,
            "request_url": ECB_URL,
            "frequency": "daily reference observations",
            "base": "EUR",
            "currencies": list(CURRENCIES),
            "rows": rows,
            "adjustment": "Published units per EUR; cross rates are derived from the same daily reference set. Not executable bid/ask quotes.",
            "caveat": "ECB rates are for information, not transaction pricing. Cross rates derived from one base cannot establish independent triangular arbitrage. Publication is around 16:00 CET on reference publication days; observation dates are not intraday trading timestamps.",
            "sha256": hashlib.sha256(
                json.dumps(rows, sort_keys=True).encode()
            ).hexdigest(),
        }

    return cached("fx_ecb_history", load, refresh)


def pair_rows(history, pair):
    try:
        base, quote = pair.split("/")
    except (ValueError, AttributeError):
        raise ValueError("Expected BASE/QUOTE currency pair")
    if base not in CURRENCIES or quote not in CURRENCIES or base == quote:
        raise ValueError("Unsupported FX pair")
    return [
        {"date": r["date"], "close": r["rates"][quote] / r["rates"][base]}
        for r in history.get("rows", [])
        if base in r["rates"] and quote in r["rates"]
    ]


def fx_overview():
    h = reference_history()
    items = []
    for pair in PAIRS:
        rows = pair_rows(h, pair)
        if not rows:
            items.append({"pair": pair, "error": "Reference history unavailable"})
            continue
        last = rows[-1]
        age = (
            dt.datetime.now(dt.timezone.utc).date()
            - dt.date.fromisoformat(last["date"])
        ).days
        items.append(
            {
                "pair": pair,
                "last": last["close"],
                "date": last["date"],
                "change": (
                    last["close"] / rows[-2]["close"] - 1 if len(rows) > 1 else None
                ),
                "month_return": (
                    last["close"] / rows[-22]["close"] - 1 if len(rows) > 21 else None
                ),
                "stale": age > 5 or h.get("cache_status") == "stale",
                "spark": [r["close"] for r in rows[-40:]],
                "rows": rows[-252:],
            }
        )
    latest = (h.get("rows") or [None])[-1]
    matrix = []
    if latest:
        for base in CURRENCIES:
            matrix.append(
                {
                    "base": base,
                    **{
                        quote: (
                            latest["rates"][quote] / latest["rates"][base]
                            if base in latest["rates"] and quote in latest["rates"]
                            else None
                        )
                        for quote in CURRENCIES
                    },
                }
            )
    return {
        "pairs": items,
        "matrix": matrix,
        "currencies": list(CURRENCIES),
        "date": latest["date"] if latest else None,
        "source": {k: v for k, v in h.items() if k != "rows"},
        "arbitrage_status": "NOT ESTABLISHED FROM REFERENCE RATES",
        "notice": "ECB reference and derived cross rates are for research, not executable quotes. Use the separate bid/ask checker for conditional opportunity screening.",
    }


def public_book(pair):
    url = (
        "https://api.kraken.com/0/public/Depth?pair="
        + pair.replace("/", "")
        + "&count=10"
    )
    started = time.time()
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "AlphaScope-Research/1.0"}),
        timeout=12,
    ) as r:
        data = json.loads(r.read())
        server_date = r.headers.get("Date")
    if data.get("error"):
        raise ValueError("; ".join(data["error"]))
    book = next(iter(data["result"].values()))
    bid, ask = book["bids"][0], book["asks"][0]
    return {
        "pair": pair,
        "bid": float(bid[0]),
        "ask": float(ask[0]),
        "bid_base_size": float(bid[1]),
        "ask_base_size": float(ask[1]),
        "bid_level_timestamp": float(bid[2]),
        "ask_level_timestamp": float(ask[2]),
        "observed_at": now(),
        "observed_epoch": time.time(),
        "request_started_epoch": started,
        "server_date": server_date,
        "url": url,
        "provider": "Kraken public fiat spot order book",
        "caveat": "Independent REST snapshots, not an atomic synchronized or firm executable quote set. Price-level timestamps describe updates, not a guarantee of current executable liquidity.",
    }


def scan_triangles(
    quotes, start="USD", notional=1000.0, fee_bps=20.0, slippage_bps=2.0, as_of=None
):
    if start not in ("USD", "EUR", "GBP"):
        raise ValueError("Start currency must be USD, EUR or GBP")
    values = [notional, fee_bps, slippage_bps]
    if any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError("Finite numeric notional and costs required")
    if (
        not 1 <= notional <= 1e7
        or not 0 <= fee_bps <= 100
        or not 0 <= slippage_bps <= 100
    ):
        raise ValueError("Notional 1–10,000,000; costs 0–100 bps per leg")
    by_pair = {q["pair"]: q for q in quotes}
    required = {"EUR/USD", "EUR/GBP", "GBP/USD"}
    if set(by_pair) != required:
        raise ValueError("Exactly EUR/USD, EUR/GBP and GBP/USD quotes are required")
    stamp = time.time() if as_of is None else as_of
    valid = True
    quality = []
    for q in quotes:
        for field in ("bid", "ask", "bid_base_size", "ask_base_size", "observed_epoch"):
            if (
                not isinstance(q.get(field), (int, float))
                or not math.isfinite(q[field])
                or q[field] <= 0
            ):
                raise ValueError("Invalid order-book numeric field")
        if q["bid"] > q["ask"]:
            raise ValueError("Crossed book is not accepted as a valid quote")
        age = stamp - q["observed_epoch"]
        if age < -0.1 or age > 10:
            valid = False
            quality.append(q["pair"] + " snapshot older than 10s or future-dated")
        if not q.get("server_date"):
            valid = False
            quality.append(q["pair"] + " HTTP server timestamp unavailable")
        if q.get("server_date"):
            try:
                if (
                    abs(stamp - parsedate_to_datetime(q["server_date"]).timestamp())
                    > 15
                ):
                    valid = False
                    quality.append(q["pair"] + " HTTP server timestamp outside 15s")
            except (TypeError, ValueError):
                valid = False
                quality.append(q["pair"] + " HTTP timestamp unreadable")
    skew = max(q["observed_epoch"] for q in quotes) - min(
        q["observed_epoch"] for q in quotes
    )
    if skew > 2:
        valid = False
        quality.append("Snapshot arrival skew exceeds 2s")
    other = [c for c in ("USD", "EUR", "GBP") if c != start]
    routes = []
    for a, b in [other, other[::-1]]:
        currencies = [start, a, b, start]
        amount = float(notional)
        gross_amount = float(notional)
        legs = []
        capacity = True
        for src, dst in zip(currencies, currencies[1:]):
            direct = by_pair.get(src + "/" + dst)
            q = direct or by_pair[dst + "/" + src]
            selling = direct is not None
            factor = q["bid"] if selling else 1 / q["ask"]
            max_source = (
                q["bid_base_size"] if selling else q["ask_base_size"] * q["ask"]
            )
            capacity = capacity and amount <= max_source + 1e-10
            before = amount
            gross_amount *= factor
            amount = (
                amount * factor * (1 - fee_bps / 10000) * (1 - slippage_bps / 10000)
            )
            legs.append(
                {
                    "from": src,
                    "to": dst,
                    "pair": q["pair"],
                    "side": "sell base at bid" if selling else "buy base at ask",
                    "price": q["bid"] if selling else q["ask"],
                    "input": before,
                    "output_after_assumed_costs": amount,
                    "top_level_source_capacity": max_source,
                    "capacity_ok": before <= max_source + 1e-10,
                    "source_url": q.get("url"),
                }
            )
        net = amount / notional - 1
        positive = valid and capacity and net > 1e-10
        status = (
            "POSITIVE NET CANDIDATE / EXECUTION UNVERIFIED"
            if positive
            else (
                "QUOTE QUALITY INSUFFICIENT"
                if not valid
                else (
                    "TOP-LEVEL CAPACITY INSUFFICIENT"
                    if not capacity
                    else "NO POSITIVE NET CANDIDATE"
                )
            )
        )
        routes.append(
            {
                "route": " → ".join(currencies),
                "start_currency": start,
                "notional": notional,
                "gross_return_using_bid_ask": gross_amount / notional - 1,
                "net_return_under_assumptions": net,
                "final_amount": amount,
                "difference": amount - notional,
                "top_level_capacity_ok": capacity,
                "positive_candidate": positive,
                "execution_verified": False,
                "status": status,
                "legs": legs,
            }
        )
    return {
        "as_of_epoch": stamp,
        "routes": routes,
        "quotes": quotes,
        "quote_quality_ok": valid,
        "quality_issues": quality,
        "arrival_skew_seconds": skew,
        "fee_bps_per_leg": fee_bps,
        "slippage_bps_per_leg": slippage_bps,
        "executable_arbitrage_verified": False,
        "notice": "Conditional arithmetic screening only. No guaranteed or verified executable arbitrage. Independent public snapshots are not atomic; account eligibility, balances, minimum orders, fee currency, execution latency, depth changes and settlement remain unchecked. Fees and slippage are user assumptions deducted from output on each leg. No orders are placed. This snapshot scanner has no historical tick-level P&L backtest.",
    }


def fx_arbitrage(payload):
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        quotes = list(pool.map(public_book, ("EUR/USD", "EUR/GBP", "GBP/USD")))
    return scan_triangles(
        quotes,
        payload.get("start", "USD"),
        float(payload.get("notional", 1000)),
        float(payload.get("fee_bps", 20)),
        float(payload.get("slippage_bps", 2)),
    )
