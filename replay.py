"""Source-backed historical portfolio replay with delayed decisions and three paths."""

import concurrent.futures
import copy
import datetime as dt
import math
import threading
import time
import uuid
import numpy as np
import pandas as pd
from data_service import prices, now
from engine import indicators, metrics

SYMBOLS = ("SPY", "GLD", "USO", "TLT")
SCENARIOS = {
    "2020-storm": {
        "name": "The 2020 volatility storm",
        "start": "2020-02-19",
        "end": "2020-05-15",
        "release_date": "2020-03-15",
        "headline": "Federal Reserve cuts its policy target to 0–0.25%",
        "source": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm",
        "published_at": "2020-03-15T17:00:00-04:00",
    },
    "2022-rates": {
        "name": "The 2022 rate-shift world",
        "start": "2022-03-15",
        "end": "2022-06-30",
        "release_date": "2022-03-16",
        "headline": "Federal Reserve raises its policy target to 0.25–0.50%",
        "source": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
        "published_at": "2022-03-16T14:00:00-04:00",
    },
}
DEFAULT_WEIGHTS = {"SPY": 0.6, "GLD": 0.15, "USO": 0.1, "TLT": 0.1}
_sessions = {}
_lock = threading.RLock()


def validate_weights(value):
    if not isinstance(value, dict) or set(value) - set(SYMBOLS):
        raise ValueError(
            "Only SPY, GLD, USO and TLT weights are supported; the remainder is cash."
        )
    result = {s: float(value.get(s, 0)) for s in SYMBOLS}
    if (
        any(not math.isfinite(v) or v < 0 or v > 1 for v in result.values())
        or sum(result.values()) > 1 + 1e-10
    ):
        raise ValueError(
            "Weights must be finite, nonnegative, and sum to no more than 100%."
        )
    return result


def rebalance(cash, units, levels, weights, rate):
    """Solve post-fee NAV for all simultaneous trades, including both sides."""
    assets = np.asarray(units) * np.asarray(levels)
    nav = float(cash + assets.sum())
    w = np.asarray(weights)
    if nav <= 0:
        raise ValueError("Portfolio has no positive equity.")
    low, high = nav * max(0.0, 1 - 2 * rate), nav
    for _ in range(60):
        mid = (low + high) / 2
        residual = mid + rate * np.abs(w * mid - assets).sum() - nav
        if residual > 0:
            high = mid
        else:
            low = mid
    after = (low + high) / 2
    new_assets = w * after
    signed = new_assets - assets
    fee = float(rate * np.abs(signed).sum())
    new_cash = float(nav - fee - new_assets.sum())
    return new_cash, new_assets / np.asarray(levels), fee, signed


def make_session(scenario_key, weights=None, budget=0.2, datasets=None):
    if scenario_key not in SCENARIOS:
        raise ValueError("Unknown historical world.")
    weights = validate_weights(DEFAULT_WEIGHTS if weights is None else weights)
    if not math.isfinite(budget) or not 0.05 <= budget <= 0.5:
        raise ValueError("Drawdown budget must be 5–50%.")
    case = SCENARIOS[scenario_key]
    if datasets is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            datasets = dict(
                zip((*SYMBOLS, "^VIX"), pool.map(prices, (*SYMBOLS, "^VIX")))
            )
    for symbol in SYMBOLS:
        if not datasets.get(symbol, {}).get("rows"):
            raise ValueError(
                f"{symbol} history unavailable. No synthetic replay is substituted."
            )
    series = [
        pd.Series({r["date"]: r["close"] for r in datasets[s]["rows"]}, name=s)
        for s in SYMBOLS
    ]
    full = pd.concat(series, axis=1).dropna().sort_index()
    full = full.loc[full.index <= case["end"]]
    if full.empty:
        raise ValueError("No common historical observations.")
    available = np.flatnonzero(full.index >= case["start"])
    if len(available) < 20:
        raise ValueError("Insufficient completed history for this world.")
    start = int(available[0])
    if start < 63:
        raise ValueError("Insufficient pre-world warm-up history.")
    spy = indicators(full["SPY"].to_numpy())
    scale = []
    for i in range(len(full)):
        row = spy.iloc[i]
        if pd.isna(row.volatility) or pd.isna(row.sma60):
            scale.append(0.0)
        else:
            scale.append(
                float(
                    min(1.0, 0.12 / max(row.volatility, 1e-8))
                    * (1 if row.price >= row.sma60 else 0.25)
                )
            )
    cash = 100000.0
    paths = {
        k: {
            "cash": cash,
            "units": np.zeros(len(SYMBOLS)),
            "returns": [],
            "cost": 0.0,
            "turnover": 0.0,
            "fills": [],
        }
        for k in ("player", "hold", "rule")
    }
    return {
        "scenario_key": scenario_key,
        "scenario": case,
        "dates": list(full.index),
        "levels": full.to_numpy(),
        "spy_indicators": spy,
        "scale": scale,
        "vix": {
            r["date"]: r["close"] for r in datasets.get("^VIX", {}).get("rows", [])
        },
        "sources": [
            {k: v for k, v in datasets[s].items() if k != "rows"}
            for s in (*SYMBOLS, "^VIX")
            if s in datasets
        ],
        "start": start,
        "pos": start,
        "turn": 0,
        "budget": budget,
        "initial_weights": weights,
        "last_weights": weights,
        "paths": paths,
        "curve": [
            {"date": str(full.index[start]), "player": cash, "hold": cash, "rule": cash}
        ],
        "decisions": [],
        "created_at": now(),
        "created_monotonic": time.monotonic(),
        "fee_bps": 5.0,
        "slippage_bps": 5.0,
        "started": False,
        "complete": False,
    }


def advance(session, weights=None, action="hold", expected_turn=None):
    if session["complete"]:
        raise ValueError("This replay is finished. Start a new world.")
    if expected_turn != session["turn"]:
        raise ValueError(
            "This turn was already processed or is out of date. Reload the replay."
        )
    if action not in ("hold", "rebalance"):
        raise ValueError("Unknown decision.")
    target = validate_weights(weights) if action == "rebalance" else None
    if not session["started"] and target is None:
        target = session["initial_weights"]
    pos = session["pos"]
    end = min(pos + 10, len(session["dates"]) - 1)
    decision_date = str(session["dates"][pos])
    rate = (session["fee_bps"] + session["slippage_bps"]) / 10000
    for i in range(pos + 1, end + 1):
        levels = session["levels"][i]
        final = i == len(session["dates"]) - 1
        day = str(session["dates"][i])
        previous = session["curve"][-1]
        values = {"date": day}
        for key, path in session["paths"].items():
            w = None
            if final:
                w = {s: 0.0 for s in SYMBOLS}
            elif key == "player" and i == pos + 1:
                w = target
            elif key == "hold" and i == session["start"] + 1:
                w = session["initial_weights"]
            elif key == "rule":
                w = {
                    s: session["initial_weights"][s] * session["scale"][i - 1]
                    for s in SYMBOLS
                }
            nav_before = float(path["cash"] + (path["units"] * levels).sum())
            if w is not None:
                cash, units, cost, signed = rebalance(
                    path["cash"], path["units"], levels, [w[s] for s in SYMBOLS], rate
                )
                path.update(cash=cash, units=units)
                path["cost"] += cost
                path["turnover"] += float(np.abs(signed).sum() / nav_before)
                for j, amount in enumerate(signed):
                    if abs(amount) > 1e-7:
                        path["fills"].append(
                            {
                                "date": day,
                                "decision_date": (
                                    str(session["dates"][i - 1])
                                    if key == "rule"
                                    else (
                                        decision_date
                                        if key == "player"
                                        else str(session["dates"][session["start"]])
                                    )
                                ),
                                "symbol": SYMBOLS[j],
                                "side": "buy" if amount > 0 else "sell",
                                "notional_usd": float(abs(amount)),
                                "cost_usd": float(abs(amount) * rate),
                                "adjusted_price": float(levels[j]),
                                "terminal_liquidation": final,
                            }
                        )
            nav = float(path["cash"] + (path["units"] * levels).sum())
            path["returns"].append(nav / previous[key] - 1)
            values[key] = nav
        session["curve"].append(values)
    session["decisions"].append(
        {
            "turn": session["turn"],
            "observed_date": decision_date,
            "execution_date": str(session["dates"][pos + 1]),
            "action": action,
            "target_weights": target,
            "revealed_through": str(session["dates"][end]),
        }
    )
    session.update(
        pos=end,
        turn=session["turn"] + 1,
        started=True,
        complete=end == len(session["dates"]) - 1,
    )
    if target is not None:
        session["last_weights"] = target
    return snapshot(session)


def _snapshot(session):
    pos = session["pos"]
    day = str(session["dates"][pos])
    row = session["spy_indicators"].iloc[pos]
    result_paths = {}
    for name, p in session["paths"].items():
        nav = session["curve"][-1][name]
        result_paths[name] = {
            "nav": nav,
            "metrics": metrics(p["returns"]) | {"trade_count": None, "win_rate": None},
            "execution_fill_count": len(p["fills"]),
            "cost_usd": p["cost"],
            "turnover": p["turnover"],
            "fills": p["fills"],
            "weights": {
                s: float(p["units"][j] * session["levels"][pos, j] / nav)
                for j, s in enumerate(SYMBOLS)
            },
            "cash_weight": float(p["cash"] / nav),
        }
    case = session["scenario"]
    release = None
    if day >= case["release_date"]:
        release = {
            "title": case["headline"],
            "published_at": case["published_at"],
            "url": case["source"],
            "source": "Federal Reserve",
            "note": "Historical release, revealed only after publication. Not a causal attribution or an automatic trade signal.",
        }
    mdd = result_paths["player"]["metrics"]["max_drawdown"] or 0
    visible = [
        {
            "date": str(session["dates"][i]),
            **{s: float(session["levels"][i, j]) for j, s in enumerate(SYMBOLS)},
        }
        for i in range(max(0, pos - 59), pos + 1)
    ]
    return {
        "id": session.get("id"),
        "scenario_key": session["scenario_key"],
        "scenario_name": case["name"],
        "as_of": day,
        "turn": session["turn"],
        "complete": session["complete"],
        "progress": (pos - session["start"])
        / (len(session["dates"]) - 1 - session["start"]),
        "revealed_sessions": pos - session["start"],
        "initial_capital": 100000.0,
        "initial_weights": session["initial_weights"],
        "last_weights": session["last_weights"],
        "budget": session["budget"],
        "budget_used": abs(mdd) / session["budget"],
        "budget_breached": abs(mdd) > session["budget"],
        "vix": session["vix"].get(day),
        "spy_sma60": None if pd.isna(row.sma60) else float(row.sma60),
        "spy_volatility": None if pd.isna(row.volatility) else float(row.volatility),
        "observations": visible,
        "curve": session["curve"],
        "paths": result_paths,
        "decisions": session["decisions"],
        "historical_release": release,
        "sources": session["sources"],
        "assumptions": [
            "Known historical replay for learning, not blind or untouched out-of-sample validation. Current-vintage adjusted histories can include later corporate-action revisions. Future observations are withheld by the replay API, but the research app has other historical-data pages.",
            "Decision after the displayed close executes at the next common session close; the existing holdings earn the intervening return. Each turn reveals up to 10 completed common sessions.",
            "Initial purchase takes place at the first next-session close. The buy-and-hold path retains the same initial allocations without rebalancing. All paths liquidate at the final close.",
            "The fixed risk rule scales the initial allocation using previous-session SPY data: min(1,12%/20-day annualized volatility), multiplied by 1 above its 60-day average or 0.25 below. Fixed heuristic, not optimized or guaranteed superior.",
            "Every buy and sell pays 5 bps fee plus 5 bps slippage; simultaneous multi-asset fees are solved against post-cost NAV. Idle cash earns zero. No leverage, taxes, impact, contract rolls or broker fills.",
            "GLD, USO and TLT are ETF exposures. Adjusted-price unit accounting is for research; no gold, oil or VIX futures P&L is claimed.",
            "The drawdown budget is a user-defined game/risk threshold. It is not a probability, stop-loss order, margin calculation or a guaranteed loss limit.",
            "News is limited to timestamped historical Fed releases shown only after publication. Current news and current FRED snapshots never enter the replay.",
        ],
        "fee_bps": session["fee_bps"],
        "slippage_bps": session["slippage_bps"],
    }


def snapshot(session):
    return copy.deepcopy(_snapshot(session))


def start_game(payload):
    s = make_session(
        payload.get("scenario", "2020-storm"),
        payload.get("weights"),
        float(payload.get("budget", 0.2)),
    )
    with _lock:
        for sid in list(_sessions):
            if time.monotonic() - _sessions[sid]["created_monotonic"] > 7200:
                del _sessions[sid]
        if len(_sessions) >= 32:
            del _sessions[next(iter(_sessions))]
        s["id"] = uuid.uuid4().hex
        _sessions[s["id"]] = s
        return snapshot(s)


def advance_game(payload):
    with _lock:
        s = _sessions.get(payload.get("id"))
        if s is None:
            raise ValueError(
                "Replay session expired or server restarted. Start a new world."
            )
        return advance(
            s,
            payload.get("weights"),
            payload.get("action", "hold"),
            payload.get("expected_turn"),
        )
