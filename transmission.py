"""A hypothesis map connected to sourced event records and descriptive evidence.
Edges are unestimated conjectures, never learned causal effects or forecasts.
"""

import concurrent.futures
import copy
from data_service import ASSETS, prices, now
from politics import EVENTS, event_study
from replay import validate_weights, DEFAULT_WEIGHTS

BACKGROUND = [
    {
        "title": "Federal Reserve: monetary-policy goals and transmission",
        "url": "https://www.federalreserve.gov/monetarypolicy/monetary-policy-what-are-its-goals-how-does-it-work.htm",
        "role": "General background, not evidence for a causal effect in the selected event",
        "verified_on": "2026-11-14",
    },
    {
        "title": "ECB: transmission mechanism and uncertain effects",
        "url": "https://www.ecb.europa.eu/mopo/intro/transmission/html/index.en.html",
        "role": "General background, not an estimated event-specific relationship",
        "verified_on": "2026-11-14",
    },
]
MAP_EVENTS = {
    "2026-midterms": EVENTS["2026-midterms"]
    | {
        "kind": "election",
        "fact": "The FEC calendar identifies 3 November 2026 as the federal general-election date. This record does not identify winners or establish a policy change.",
        "source_role": "Official election calendar",
        "verified_on": "2026-11-14",
    },
    "2022-midterms": EVENTS["2022-midterms"]
    | {
        "kind": "election",
        "fact": "The FEC congressional-candidate guide identifies 8 November 2022 as the general-election date. No party-specific market effect is inferred.",
        "source_role": "Official election-date reference",
        "verified_on": "2026-11-14",
    },
    "2022-rate-hike": {
        "date": "2022-03-16",
        "name": "2022 Federal Reserve rate increase",
        "kind": "monetary",
        "fact": "On 16 March 2022, the FOMC raised its federal-funds target range to 0.25–0.50%. The statement was published at 2 p.m. EDT.",
        "source": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
        "source_role": "Official FOMC statement",
        "published_at": "2022-03-16T14:00:00-04:00",
        "verified_on": "2026-11-14",
    },
}
ROLES = {
    "SPY": "Broad US equity exposure; not a sector-level holdings look-through",
    "GLD": "Gold ETF proxy; not a gold futures contract",
    "USO": "Oil ETF proxy with fund/roll effects; not spot oil or executable futures P&L",
    "TLT": "Long-duration Treasury ETF exposure; not a guaranteed hedge",
}


def graph_for(event):
    election = event["kind"] == "election"
    nodes = [
        {
            "id": "event",
            "label": "Official event record",
            "kind": "fact",
            "summary": event["fact"],
            "question": "What actually happened, and when?",
            "counter": "A calendar date does not establish a winner, an enacted policy or a market cause. Even an official policy announcement may have been anticipated.",
            "sources": [
                {
                    "title": event["source_role"],
                    "url": event["source"],
                    "role": "Event record",
                    "verified_on": event["verified_on"],
                }
            ],
        },
        {
            "id": "policy",
            "label": "Policy expectations",
            "kind": "hypothesis",
            "summary": (
                "A change in congressional composition could alter expectations for taxation, spending or trade. Enactment, timing and prior pricing matter."
                if election
                else "The announcement could change expectations for future policy rates and the balance sheet; the unexpected component matters more than a known decision."
            ),
            "question": "Did expectations change beyond what was already priced?",
            "counter": "No enacted tax, spending or trade change is established by this map. Anticipation, gridlock or unchanged expectations could weaken this link.",
            "sources": BACKGROUND,
        },
        {
            "id": "rates",
            "label": "Discount rates & credit",
            "kind": "hypothesis",
            "summary": "Changes in expected financing costs or discount rates could affect valuations and bond prices, all else equal. The market response need not match the policy-rate change.",
            "question": "Which yields or financing terms actually changed?",
            "counter": "Growth, inflation, term premia and safe-haven demand can move longer yields in another direction. This map has no historical yield-vintage causal model.",
            "sources": BACKGROUND,
        },
        {
            "id": "earnings",
            "label": "Margins & earnings",
            "kind": "hypothesis",
            "summary": "Taxes, demand, trade costs and financing conditions could affect expected company cash flows differently across industries.",
            "question": "Is there company-level evidence for the proposed cash-flow channel?",
            "counter": "Pricing power, hedging, foreign revenues and earnings announcements can offset the proposed effect. No company earnings estimate is generated.",
            "sources": BACKGROUND,
        },
        {
            "id": "sentiment",
            "label": "Risk appetite & VIX",
            "kind": "hypothesis",
            "summary": "Policy uncertainty or its resolution could change demand for risk and options protection. VIX is expected volatility, not a prediction of stock direction.",
            "question": "Does the observed VIX window support or challenge the uncertainty story?",
            "counter": "Inflation releases, earnings, geopolitical events and positioning can also move VIX. A fall in VIX does not identify its cause.",
            "sources": [
                {
                    "title": "Cboe VIX historical data",
                    "url": "https://www.cboe.com/tradable-products/vix/vix-historical-data",
                    "role": "Index definition / historical provider",
                }
            ],
        },
        {
            "id": "sectors",
            "label": "Observed sector windows",
            "kind": "observation",
            "summary": "Inspect adjusted ETF returns and SPY differences around the event. These are descriptive observations, not measurements of the arrows above.",
            "question": "What did the available prices actually do?",
            "counter": "Co-occurring returns do not prove causality. Three selected events are insufficient to validate a robust political trading rule. Future sessions remain unavailable.",
            "sources": [],
        },
        {
            "id": "portfolio",
            "label": "Your proposed exposure",
            "kind": "user_input",
            "summary": "Map your entered SPY, GLD, USO and TLT target weights to broad asset exposures; the remainder is cash. No predicted loss or event-specific price sensitivity is calculated.",
            "question": "Which exposures would you investigate before changing your allocation?",
            "counter": "This does not look through ETF holdings, estimate correlations or produce a portfolio forecast. User weights do not alter historical market evidence.",
            "sources": [
                {
                    "title": "User-entered target weights",
                    "role": "User assumption, not an observed portfolio",
                }
            ],
        },
    ]
    pairs = [
        ("event", "policy"),
        ("policy", "rates"),
        ("policy", "earnings"),
        ("policy", "sentiment"),
        ("rates", "sectors"),
        ("earnings", "sectors"),
        ("sentiment", "sectors"),
        ("sectors", "portfolio"),
    ]
    edges = [
        {
            "from": a,
            "to": b,
            "kind": "exposure_mapping" if b == "portfolio" else "hypothesized_channel",
            "estimated": False,
            "label": (
                "Exposure questions, not forecast P&L"
                if b == "portfolio"
                else "Possible channel; not an estimated causal link"
            ),
        }
        for a, b in pairs
    ]
    return nodes, edges


def transmission_map(event_key="2026-midterms", weights=None, window=20, datasets=None):
    if event_key not in MAP_EVENTS:
        raise ValueError("Unknown map event.")
    if type(window) is not int or not 5 <= window <= 60:
        raise ValueError("Window must be an integer from 5 to 60 sessions.")
    weights = validate_weights(DEFAULT_WEIGHTS if weights is None else weights)
    event = copy.deepcopy(MAP_EVENTS[event_key])
    nodes, edges = graph_for(event)
    symbols = (
        ["SPY", "GLD", "USO", "TLT"]
        + [s for s, (_, category) in ASSETS.items() if category == "Sector"]
        + ["^VIX"]
    )
    if datasets is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            datasets = dict(zip(symbols, pool.map(prices, symbols)))
    benchmark = datasets.get("SPY", {})
    vix = datasets.get("^VIX", {})
    observations = []
    for symbol in symbols:
        if symbol == "^VIX":
            continue
        data = datasets.get(symbol, {})
        base = {
            "symbol": symbol,
            "name": ASSETS.get(symbol, (symbol, ""))[0],
            "category": ASSETS.get(symbol, ("", ""))[1],
        }
        try:
            if not data.get("rows") or not benchmark.get("rows"):
                raise ValueError(
                    "Asset or SPY history unavailable; no observation substituted."
                )
            result = event_study(
                data["rows"], benchmark["rows"], vix.get("rows"), event["date"], window
            )
            observations.append(
                base
                | {
                    "summary": result["summary"],
                    "complete": result["complete"],
                    "available_post_sessions": result["available_post_sessions"],
                    "baseline_date": result["baseline_date"],
                    "event_session": result["event_session"],
                    "curve": result["curve"],
                    "methodology": result["methodology"],
                    "sources": [
                        {k: v for k, v in d.items() if k != "rows"}
                        for d in [data, benchmark, vix]
                    ],
                }
            )
        except (ValueError, KeyError, TypeError) as e:
            observations.append(
                base | {"error": str(e), "summary": None, "complete": False}
            )
    exposure = [
        {"symbol": s, "weight": w, "role": ROLES[s], "source": "User input"}
        for s, w in weights.items()
    ]
    sector_count = sum(
        o["category"] == "Sector" and o["summary"] is not None for o in observations
    )
    for node in nodes:
        if node["id"] == "sectors":
            node["availability"] = f"{sector_count} of 11 sector histories available"
    return {
        "event_key": event_key,
        "event": event,
        "catalog": [
            {"key": k, "name": v["name"], "date": v["date"]}
            for k, v in MAP_EVENTS.items()
        ],
        "nodes": nodes,
        "edges": edges,
        "observations": observations,
        "exposure": exposure,
        "cash_weight": max(0.0, 1 - sum(weights.values())),
        "window": window,
        "generated_at": now(),
        "background_sources": BACKGROUND,
        "causal_effects_estimated": False,
        "portfolio_forecast_available": False,
        "notice": "A research hypothesis map, not a causal model, forecast or trading recommendation. Official event records, conjectured channels, descriptive price observations and user inputs are different evidence types. Every edge is unestimated. Current news is not used to generate past trading signals. Historical windows use current-vintage adjusted prices; incomplete future windows are labelled partial.",
    }
