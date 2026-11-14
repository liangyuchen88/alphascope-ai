"""Explainable display alerts. Heuristic thresholds; no automatic orders or forecasts."""

import datetime as dt
import math

RULES = [
    {
        "id": "vix",
        "name": "VIX stress",
        "warning": 20.0,
        "critical": 30.0,
        "units": "index points",
        "basis": "Illustrative display bands. VIX is implied volatility, not a directional forecast or investable return.",
    },
    {
        "id": "realized_vol",
        "name": "SPY realized volatility",
        "warning": 0.25,
        "critical": 0.35,
        "units": "annualized fraction",
        "basis": "20-return sample volatility. Fixed review thresholds, not an optimized strategy.",
    },
    {
        "id": "day_loss",
        "name": "SPY one-session loss",
        "warning": 0.02,
        "critical": 0.03,
        "units": "loss fraction",
        "basis": "Adjacent completed observations; backward-looking, not a future-loss prediction.",
    },
    {
        "id": "trend",
        "name": "SPY below 60-session average",
        "warning": 0.0,
        "critical": None,
        "units": "close minus SMA",
        "basis": "A descriptive trend flag. It can whipsaw and does not require selling.",
    },
    {
        "id": "concentration",
        "name": "Largest ETF target / holding",
        "warning": 0.60,
        "critical": 0.80,
        "units": "portfolio weight",
        "basis": "ETF-level exposure only, not issuer-level look-through, correlation or diversified portfolio risk.",
    },
    {
        "id": "drawdown",
        "name": "Replay drawdown budget use",
        "warning": 0.80,
        "critical": 1.0,
        "units": "fraction of user budget",
        "basis": "Historical maximum drawdown divided by user budget. No automatic stop or guarantee.",
    },
    {
        "id": "stale",
        "name": "Market data age",
        "warning": 5,
        "critical": None,
        "units": "calendar days",
        "basis": "Age above five calendar days, or a failed refresh, suppresses the affected current-market risk calculations.",
    },
]


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def evidence(source, observed=None):
    return {
        k: source.get(k)
        for k in ("symbol", "provider", "url", "retrieved_at", "sha256")
    } | {"observed_date": observed or source.get("date")}


def alert(
    rule_id,
    severity,
    title,
    detail,
    value,
    threshold,
    units,
    date,
    sources,
    review,
    category="market",
):
    return {
        "id": rule_id,
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
        "value": value,
        "threshold": threshold,
        "units": units,
        "observed_date": date,
        "sources": sources,
        "review": review,
        "automatic_action": False,
    }


def level(value, warning, critical, inclusive=True):
    if not finite(value):
        return None

    def crossed(threshold):
        return value >= threshold - 1e-12 if inclusive else value > threshold + 1e-10

    if crossed(critical):
        return "critical"
    if crossed(warning):
        return "warning"
    return None


def market_checks(spy, vix, date, spy_sources, vix_sources):
    items = []
    v = level(vix, 20, 30)
    if v:
        items.append(
            alert(
                "vix",
                v,
                "VIX stress band triggered",
                f'Observed VIX {vix:.2f}; review band begins at {20 if v=="warning" else 30} points. This is not a forecast of market direction.',
                vix,
                20 if v == "warning" else 30,
                "index points",
                date,
                vix_sources,
                "Inspect the dated VIX history and how much volatility your plan can tolerate.",
            )
        )
    vol = spy.get("volatility")
    v = level(vol, 0.25, 0.35)
    if v:
        items.append(
            alert(
                "realized_vol",
                v,
                "Realized volatility is elevated",
                f"SPY 20-return annualized volatility is {vol:.1%}.",
                vol,
                0.25 if v == "warning" else 0.35,
                "annualized fraction",
                spy.get("date", date),
                spy_sources,
                "Review position size and compare costs and drawdowns; the threshold is an educational assumption.",
            )
        )
    change = spy.get("change")
    loss = -change if finite(change) else None
    v = level(loss, 0.02, 0.03)
    if v:
        items.append(
            alert(
                "day_loss",
                v,
                "Large observed SPY session loss",
                f"The latest adjacent-observation return is {change:.2%}.",
                loss,
                0.02 if v == "warning" else 0.03,
                "loss fraction",
                spy.get("date", date),
                spy_sources,
                "Inspect the session and price source. A past loss does not imply the next session will also fall.",
            )
        )
    close, sma = spy.get("last"), spy.get("sma60")
    if finite(close) and finite(sma) and close < sma:
        items.append(
            alert(
                "trend",
                "warning",
                "SPY is below its 60-session average",
                f"Observed close {close:.2f}; 60-session average {sma:.2f}.",
                close - sma,
                0.0,
                "close minus SMA",
                spy.get("date", date),
                spy_sources,
                "Read the trend evidence and counterevidence. Sideways markets can repeatedly trigger this rule.",
            )
        )
    return items


def concentration(weights, date, sources, kind):
    usable = {s: w for s, w in (weights or {}).items() if finite(w) and w > 0}
    if not usable:
        return []
    symbol = max(usable, key=usable.get)
    weight = usable[symbol]
    severity = level(weight, 0.60, 0.80, inclusive=False)
    if not severity:
        return []
    return [
        alert(
            "concentration",
            severity,
            f"{symbol} dominates ETF {kind}",
            f"{symbol} represents {weight:.1%} of {kind}. This checks fund exposure, not underlying issuer concentration or correlations.",
            weight,
            0.60 if severity == "warning" else 0.80,
            "portfolio weight",
            date,
            sources,
            "Inspect underlying exposures and your intended allocation. One diversified ETF is different from one individual company.",
            category="portfolio",
        )
    ]


def bundle(items, context, as_of, coverage):
    counts = {
        s: sum(a["severity"] == s for a in items)
        for s in ("critical", "warning", "unavailable", "info")
    }
    status = (
        "critical"
        if counts["critical"]
        else (
            "warning"
            if counts["warning"]
            else "incomplete" if counts["unavailable"] else "no_trigger"
        )
    )
    return {
        "context": context,
        "as_of": as_of,
        "status": status,
        "counts": counts,
        "alerts": sorted(
            items,
            key=lambda a: {"critical": 0, "unavailable": 1, "warning": 2, "info": 3}[
                a["severity"]
            ],
        ),
        "rules": RULES,
        "coverage": coverage,
        "notice": "These are review alerts from explicit heuristic rules, not validated forecasts, broker orders or a claim that unflagged portfolios are safe. Evaluated when data is loaded or replay advances; no background monitoring or push notifications.",
    }


def evaluate_market_risk(data, allocation=None):
    stamp = data.get("generated_at") or dt.datetime.now(dt.timezone.utc).isoformat()
    today = dt.date.fromisoformat(stamp[:10])
    items = []
    assets = data.get("assets", [])
    spy = next((a for a in assets if a.get("symbol") == "SPY"), {})
    vx = data.get("vix", {})
    vr = (vx.get("rows") or [{}])[-1]
    vdate = vr.get("date")

    def fresh(date, source):
        try:
            age = (today - dt.date.fromisoformat(date)).days
        except (ValueError, TypeError):
            return False
        return (
            0 <= age <= 5
            and source.get("cache_status") != "stale"
            and not source.get("stale")
        )

    spy_valid = finite(spy.get("last")) and fresh(spy.get("date"), spy)
    vix_valid = finite(vr.get("close")) and fresh(vdate, vx)
    for symbol, valid, source, observed in [
        ("SPY", spy_valid, spy, spy.get("date")),
        ("VIX", vix_valid, vx, vdate),
    ]:
        if not valid:
            try:
                age = (today - dt.date.fromisoformat(observed)).days
            except (ValueError, TypeError):
                age = None
            reasons = []
            if age is None:
                reasons.append("No valid observation date")
            elif age > 5:
                reasons.append(f"Observation is {age} calendar days old (limit: 5)")
            elif age < 0:
                reasons.append("Observation date is in the future")
            if source.get("cache_status") == "stale" or source.get("stale"):
                reasons.append("Refresh failed or the source is flagged stale")
            observed_value = spy.get("last") if symbol == "SPY" else vr.get("close")
            if not finite(observed_value):
                reasons.append("No finite observation value")
            detail = "; ".join(reasons) + ". Current classification is suppressed."
            items.append(
                alert(
                    "data_" + symbol,
                    "unavailable",
                    symbol + " current assessment unavailable",
                    detail,
                    age,
                    5,
                    "calendar days",
                    observed,
                    [evidence(source, observed)],
                    "Inspect source freshness or retry the data connection. Historical data may still be inspectable.",
                    category="data",
                )
            )
    valid_spy = spy if spy_valid else {}
    items += market_checks(
        valid_spy,
        vr.get("close") if vix_valid else None,
        vdate if vix_valid else spy.get("date"),
        [evidence(spy)],
        [evidence(vx, vdate)],
    )
    if spy_valid and any(
        not finite(spy.get(k)) for k in ("sma60", "volatility", "change")
    ):
        items.append(
            alert(
                "indicator_coverage",
                "unavailable",
                "Some SPY checks lack enough history",
                "Trend, realized-volatility or session-loss inputs are missing; no value is invented.",
                None,
                None,
                "indicator coverage",
                spy.get("date"),
                [evidence(spy)],
                "Inspect history coverage before using the missing indicator.",
                category="data",
            )
        )
    stale_other = [
        a.get("symbol", "Unknown")
        for a in assets
        if a.get("symbol") != "SPY"
        and (not finite(a.get("last")) or not fresh(a.get("date"), a))
    ]
    if stale_other:
        items.append(
            alert(
                "other_data",
                "unavailable",
                "Some watchlist assets lack fresh data",
                ", ".join(stale_other),
                len(stale_other),
                0,
                "assets",
                None,
                [],
                "Do not infer current signals for these assets; inspect their source records.",
                category="data",
            )
        )
    snapshots = [s for s, d in data.get("macro", {}).items() if d.get("ingestion")]
    if snapshots:
        items.append(
            alert(
                "macro_snapshot",
                "info",
                "Macro context uses verified snapshots",
                ", ".join(snapshots)
                + " are labelled official-page snapshots, not an automatic live macro feed.",
                len(snapshots),
                None,
                "series",
                None,
                [
                    evidence(d, (d.get("rows") or [{}])[-1].get("date"))
                    for s, d in data.get("macro", {}).items()
                    if s in snapshots
                ],
                "Check observation dates in Sources & Methods. These snapshots are excluded from historical signals.",
                category="data",
            )
        )
    if allocation is not None:
        items += concentration(allocation, stamp[:10], [], "proposed targets")
    return bundle(
        items,
        "CURRENT MARKET / DAILY RESEARCH",
        stamp,
        {
            "spy": spy_valid,
            "vix": vix_valid,
            "proposed_weights": allocation,
            "portfolio": (
                "Proposed targets only; no live portfolio or broker connection"
                if allocation is not None
                else "No portfolio supplied; concentration and drawdown are not evaluated"
            ),
        },
    )


def evaluate_replay_risk(data):
    day = data["as_of"]
    sources = data.get("sources", [])
    spy_source = next((s for s in sources if s.get("symbol") == "SPY"), {})
    vix_source = next((s for s in sources if s.get("symbol") == "^VIX"), {})
    rows = data.get("observations", [])
    last = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}
    change = (
        last["SPY"] / previous["SPY"] - 1
        if finite(last.get("SPY"))
        and finite(previous.get("SPY"))
        and previous["SPY"] > 0
        else None
    )
    spy = {
        "last": last.get("SPY"),
        "date": day,
        "sma60": data.get("spy_sma60"),
        "volatility": data.get("spy_volatility"),
        "change": change,
    }
    items = market_checks(
        spy,
        data.get("vix"),
        day,
        [evidence(spy_source, day)],
        [evidence(vix_source, day)],
    )
    if not finite(data.get("vix")):
        items.append(
            alert(
                "replay_vix_missing",
                "unavailable",
                "VIX missing for the revealed session",
                "No exact-date VIX observation is available; no synthetic level is substituted.",
                None,
                None,
                "index points",
                day,
                [evidence(vix_source, day)],
                "Review the historical source. Other dated checks can still be inspected.",
                category="data",
            )
        )
    player = data["paths"]["player"]
    items += concentration(
        player.get("weights"),
        day,
        [
            evidence(s, day)
            for s in sources
            if s.get("symbol") in player.get("weights", {})
        ],
        "observed holdings",
    )
    mdd = player["metrics"].get("max_drawdown")
    budget = data.get("budget")
    if finite(mdd) and finite(budget) and budget > 0:
        used = abs(mdd) / budget
        severity = level(used, 0.8, 1.0)
        if severity:
            items.append(
                alert(
                    "drawdown",
                    severity,
                    (
                        "Realized drawdown budget reached or exceeded"
                        if severity == "critical"
                        else "Realized drawdown is near your budget"
                    ),
                    f"Maximum drawdown {abs(mdd):.2%}; user budget {budget:.2%}; budget use {used:.1%}.",
                    used,
                    1.0 if severity == "critical" else 0.8,
                    "fraction of user budget",
                    day,
                    [evidence(s, day) for s in sources if s.get("symbol") != "^VIX"],
                    "Review the realized path and alternatives. This is a historical budget alert; it does not place an automatic stop or predict a further loss.",
                    category="portfolio",
                )
            )
    return bundle(
        items,
        "HISTORICAL REPLAY / REVEALED OBSERVATIONS ONLY",
        day,
        {
            "portfolio": "Actual hypothetical holdings at the revealed close",
            "vix": finite(data.get("vix")),
            "drawdown_budget": budget,
            "freshness": "Compared with replay information date, never with today; no current-market observations are used",
        },
    )
