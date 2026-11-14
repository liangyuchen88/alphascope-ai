"""Descriptive event windows; no causal claim and no news-driven backtest."""

import concurrent.futures, datetime as dt, xml.etree.ElementTree as ET
import pandas as pd
from data_service import cached, download, prices, now

EVENTS = {
    "2026-midterms": {
        "date": "2026-11-03",
        "name": "2026 US midterm election",
        "source": "https://www.fec.gov/help-candidates-and-committees/dates-and-deadlines/2026-reporting-dates/federal-election-activity-periods-each-state-2026/",
    },
    "2022-midterms": {
        "date": "2022-11-08",
        "name": "2022 US midterm election",
        "source": "https://www.fec.gov/resources/cms-content/documents/policy-guidance/candgui.pdf",
    },
    "2018-midterms": {
        "date": "2018-11-06",
        "name": "2018 US midterm election",
        "source": "https://www.fec.gov/resources/cms-content/documents/2018pdates.pdf",
    },
}


def political_news(refresh=False):
    url = "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"

    def load():
        root = ET.fromstring(download(url))
        items = []
        for item in root.findall(".//item")[:25]:
            link = item.findtext("link", "")
            if not link.startswith(("https://www.bbc.com/", "https://www.bbc.co.uk/")):
                continue
            title = item.findtext("title", "")
            keywords = [
                "election",
                "midterm",
                "congress",
                "senate",
                "tariff",
                "trump",
                "white house",
                "democrat",
                "republican",
                "shutdown",
                "vote",
                "politic",
            ]
            tags = [k for k in keywords if k in title.lower()]
            items.append(
                {
                    "title": title,
                    "url": link,
                    "published": item.findtext("pubDate", ""),
                    "source": "BBC News",
                    "scope": "US & Canada RSS; political items highlighted",
                    "political_match": bool(tags),
                    "matched_keywords": tags,
                }
            )
        if not items:
            raise ValueError("No usable RSS items")
        return {
            "provider": "BBC News",
            "url": url,
            "source_home": "https://www.bbc.com/news",
            "terms_url": "https://www.bbc.com/usingthebbc/terms/",
            "items": items,
            "caveat": "Personal non-commercial feed reader. Original titles and publisher links; no full articles, images or generated factual summaries. Keyword tags are application annotations, not BBC classifications.",
        }

    return cached("political_news", load, refresh)


def event_study(asset_rows, benchmark_rows, vix_rows, event_date, window=20):
    if not 5 <= window <= 60:
        raise ValueError("Window must be 5–60 sessions")
    a = pd.DataFrame(asset_rows).set_index("date")["close"].astype(float)
    b = pd.DataFrame(benchmark_rows).set_index("date")["close"].astype(float)
    frame = (
        pd.concat([a.rename("asset"), b.rename("benchmark")], axis=1)
        .dropna()
        .sort_index()
    )
    if frame.empty:
        raise ValueError("No common price observations")
    eligible = frame.index[frame.index >= event_date]
    if not len(eligible):
        raise ValueError("No completed session on or after the event yet")
    anchor = eligible[0]
    pos = frame.index.get_loc(anchor)
    if pos < 1:
        raise ValueError("Pre-event baseline is unavailable")
    baseline = frame.iloc[pos - 1]
    base_date = str(frame.index[pos - 1])
    vix = {r["date"]: r["close"] for r in (vix_rows or [])}
    base_vix = vix.get(base_date)
    start = max(0, pos - window)
    end = min(len(frame), pos + window + 1)
    curve = []
    for i in range(start, end):
        date = str(frame.index[i])
        av = float(frame.iloc[i].asset / baseline.asset - 1)
        bv = float(frame.iloc[i].benchmark / baseline.benchmark - 1)
        vv = vix.get(date)
        curve.append(
            {
                "date": date,
                "session": i - pos,
                "asset": av,
                "benchmark": bv,
                "excess": av - bv,
                "vix": vv,
                "vix_change_points": (
                    float(vv - base_vix)
                    if vv is not None and base_vix is not None
                    else None
                ),
            }
        )
    post = [r for r in curve if r["session"] >= 0]
    last = post[-1]
    return {
        "event_date": event_date,
        "event_session": str(anchor),
        "baseline_date": base_date,
        "baseline_vix": base_vix,
        "requested_post_sessions": window,
        "available_post_sessions": int(last["session"]),
        "complete": last["session"] >= window,
        "curve": curve,
        "summary": {
            "asset_return": last["asset"],
            "benchmark_return": last["benchmark"],
            "excess_return": last["excess"],
            "vix_change_points": last["vix_change_points"],
            "end_date": last["date"],
        },
        "methodology": "Adjusted-price change from the last common trading close before election day. Event session is 0; post-session window ends at +N. Excess return is asset minus SPY, not factor-adjusted alpha. VIX changes are index points, not investable P&L. Coincidence does not establish causation. Macro releases, rates, earnings and positioning are confounders. No election winner, policy change or causal effect is inferred.",
    }


def study(event_key, symbol="SPY", window=20):
    if event_key not in EVENTS:
        raise ValueError("Unknown event")
    event = EVENTS[event_key]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        a, b, v = list(pool.map(prices, [symbol, "SPY", "^VIX"]))
    if "rows" not in a or "rows" not in b:
        raise ValueError("Asset or SPY history unavailable")
    result = event_study(a["rows"], b["rows"], v.get("rows"), event["date"], window)
    result.update(
        event=event,
        symbol=symbol,
        sources=[{k: val for k, val in d.items() if k != "rows"} for d in [a, b, v]],
        retrieved_at=now(),
    )
    return result
