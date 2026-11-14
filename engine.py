"""Deterministic, close-to-close research. Signals t execute t+1 close."""

import numpy as np
import pandas as pd

STRATEGIES = {
    "trend": "Trend SMA 20 / 60",
    "momentum": "63-session momentum",
    "reversion": "RSI mean reversion",
    "volatility": "Volatility target 12%",
    "rate_guard": "Rate-aware risk budget",
}


def indicators(prices):
    p = pd.Series(prices, dtype=float)
    delta = p.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.where(loss != 0, 100).where(~((gain == 0) & (loss == 0)), 50)
    return pd.DataFrame(
        {
            "price": p,
            "sma20": p.rolling(20).mean(),
            "sma60": p.rolling(60).mean(),
            "momentum": p.pct_change(63, fill_method=None),
            "rsi": rsi,
            "volatility": p.pct_change(fill_method=None).rolling(20).std()
            * np.sqrt(252),
        }
    )


def targets(prices, strategy, rate_values=None):
    x = indicators(prices)
    if strategy == "trend":
        s = (x.sma20 > x.sma60).astype(float).where(x.sma60.notna(), 0)
    elif strategy == "momentum":
        s = (x.momentum > 0).astype(float)
    elif strategy in ("volatility", "rate_guard"):
        s = (
            (0.12 / x.volatility.replace(0, np.nan))
            .clip(0, 1)
            .where(x.price > x.sma60, 0)
            .fillna(0)
        )
        if strategy == "rate_guard":
            if rate_values is None:
                raise ValueError(
                    "Short-yield history unavailable; no valid rate-aware backtest"
                )
            rates = pd.Series(rate_values, dtype=float)
            s = (s / (1 + 5 * rates.clip(lower=0) / 100)).where(rates.notna(), 0)
    elif strategy == "reversion":
        holding = 0
        values = []
        for r in x.rsi:
            if pd.notna(r):
                if r < 30:
                    holding = 1
                elif r > 55:
                    holding = 0
            values.append(holding)
        s = pd.Series(values, dtype=float)
    else:
        raise ValueError("Unknown strategy")
    return s


def metrics(returns, trades=None):
    r = np.asarray(returns, dtype=float)
    if not len(r):
        return {
            k: None
            for k in [
                "total_return",
                "cagr",
                "annual_return",
                "volatility",
                "sharpe",
                "sortino",
                "max_drawdown",
                "win_rate",
                "trade_count",
            ]
        }
    equity = np.r_[1.0, np.cumprod(1 + r)]
    vol = np.std(r, ddof=1) * np.sqrt(252) if len(r) > 1 else 0
    down = np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(252)
    result = {
        "total_return": float(equity[-1] - 1),
        "cagr": float(equity[-1] ** (252 / len(r)) - 1) if len(r) >= 252 else None,
        "annual_return": float(np.mean(r) * 252) if len(r) >= 20 else None,
        "volatility": float(vol) if len(r) >= 20 else None,
        "sharpe": (
            float(np.mean(r) * 252 / vol) if vol > 1e-12 and len(r) >= 60 else None
        ),
        "sortino": (
            float(np.mean(r) * 252 / down) if down > 1e-12 and len(r) >= 60 else None
        ),
        "max_drawdown": float(np.min(equity / np.maximum.accumulate(equity) - 1)),
    }
    closed = [t for t in (trades or []) if t.get("net_return") is not None]
    result.update(
        win_rate=(
            float(np.mean([t["net_return"] > 0 for t in closed])) if closed else None
        ),
        trade_count=len(closed),
    )
    return result


def backtest(
    rows, strategy="trend", fee_bps=5, slippage_bps=5, period="test", rate_rows=None
):
    if strategy not in STRATEGIES:
        raise ValueError("Unknown strategy")
    if not (0 <= fee_bps <= 100 and 0 <= slippage_bps <= 100):
        raise ValueError("Costs must be 0–100 bps")
    if period not in ("development", "validation", "test", "all"):
        raise ValueError("Unknown period")
    frame = pd.DataFrame(rows).copy()
    if len(frame) < 260:
        raise ValueError(
            "At least 260 daily observations are required for a valid backtest"
        )
    p = frame["close"].astype(float)
    if (
        (p <= 0).any()
        or not np.isfinite(p).all()
        or not frame.date.is_monotonic_increasing
        or frame.date.duplicated().any()
    ):
        raise ValueError("Invalid price series")
    # Fixed calendar boundaries: adding future data never moves an earlier observation into development.
    dates = pd.to_datetime(frame.date)
    if period == "development":
        mask = dates < pd.Timestamp("2023-01-01")
    elif period == "validation":
        mask = (dates >= pd.Timestamp("2023-01-01")) & (
            dates < pd.Timestamp("2024-01-01")
        )
    elif period == "test":
        mask = dates >= pd.Timestamp("2024-01-01")
    else:
        mask = pd.Series(True, index=frame.index)
    mask &= np.arange(len(frame)) >= 63
    indices = np.flatnonzero(mask)
    if len(indices) < 20:
        raise ValueError("Fewer than 20 valid sessions in the selected period")
    start, end = int(indices[0]), int(indices[-1]) + 1
    rate_values = None
    rate_alignment = []
    if strategy == "rate_guard":
        if not rate_rows:
            raise ValueError(
                "Short-yield history unavailable; no valid rate-aware backtest"
            )
        rf = pd.DataFrame(rate_rows).rename(columns={"close": "short_yield"})[
            ["date", "short_yield"]
        ]
        rf["rate_date"] = pd.to_datetime(rf["date"])
        rf = rf.drop(columns="date").sort_values("rate_date")
        aligned = pd.merge_asof(
            pd.DataFrame({"date": dates}),
            rf,
            left_on="date",
            right_on="rate_date",
            direction="backward",
            allow_exact_matches=False,
            tolerance=pd.Timedelta(days=7),
        )
        rate_values = aligned.short_yield
        if rate_values.iloc[start:end].notna().mean() < 0.95:
            raise ValueError("Short-yield coverage below 95%; no valid backtest")
        rate_alignment = [
            {
                "date": str(frame.date.iloc[i]),
                "rate_date": (
                    str(aligned.rate_date.iloc[i].date())
                    if pd.notna(aligned.rate_date.iloc[i])
                    else None
                ),
                "short_yield": (
                    float(rate_values.iloc[i])
                    if pd.notna(rate_values.iloc[i])
                    else None
                ),
            }
            for i in range(start, end)
        ]
    signals = targets(p, strategy, rate_values)
    # No inherited position at evaluation boundary. t close target -> t+1 close execution -> t+2 return.
    execution = signals.shift(1).fillna(0)
    execution.iloc[:start] = 0
    execution.iloc[end - 1] = (
        0  # Liquidate at final close, without opening a new position.
    )
    rate = (fee_bps + slippage_bps) / 10000
    cash = 1.0
    units = 0.0
    previous_nav = 1.0
    values = []
    return_values = []
    holding_values = []
    turn_values = []
    cost_values = []
    fills = []
    for i in range(start, end):
        price = float(p.iloc[i])
        invested = units * price
        nav = cash + invested
        holding_values.append(
            units * float(p.iloc[i - 1]) / previous_nav if i > start else 0.0
        )
        weight = float(execution.iloc[i])
        # Solve trade value and fee simultaneously, so fees never create negative cash.
        buying = weight * nav >= invested
        new_invested = (
            weight
            * (nav + (rate * invested if buying else -rate * invested))
            / (1 + (weight * rate if buying else -weight * rate))
        )
        notional = abs(new_invested - invested)
        cost = notional * rate
        if notional > 1e-12:
            fills.append(
                {
                    "date": str(frame.date.iloc[i]),
                    "signal_date": (
                        str(frame.date.iloc[i - 1]) if i != end - 1 else None
                    ),
                    "side": "buy" if new_invested > invested else "sell",
                    "adjusted_price": price,
                    "normalized_notional": float(notional),
                    "target_weight": weight,
                    "normalized_fee": float(notional * fee_bps / 10000),
                    "normalized_slippage": float(notional * slippage_bps / 10000),
                    "normalized_total_cost": float(cost),
                    "nav_before_cost": float(nav),
                    "terminal_liquidation": i == end - 1,
                }
            )
        cash = nav - new_invested - cost
        units = new_invested / price
        after = nav - cost
        values.append(after)
        return_values.append(after / previous_nav - 1)
        turn_values.append(notional / nav)
        cost_values.append(cost / nav)
        previous_nav = after
    eq = np.asarray(values)
    returns = np.asarray(return_values)
    benchmark = (
        p.pct_change(fill_method=None).fillna(0).iloc[start:end].to_numpy(copy=True)
    )
    benchmark[0] = 1 / (1 + rate) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - rate) - 1
    beq = np.cumprod(1 + benchmark)
    dd = eq / np.maximum.accumulate(np.r_[1.0, eq])[1:] - 1
    trades = []
    entry = None
    for i in range(start, end):
        before = float(execution.iloc[i - 1]) if i else 0
        after = float(execution.iloc[i])
        if before == 0 and after > 0:
            entry = (i, float(p.iloc[i]), after)
        if before > 0 and after == 0 and entry:
            j, price, weight = entry
            trades.append(
                {
                    "entry_date": str(frame.date.iloc[j]),
                    "exit_date": str(frame.date.iloc[i]),
                    "entry_price": price,
                    "exit_price": float(p.iloc[i]),
                    "net_return": (
                        float((p.iloc[i] / price) * (1 - rate) / (1 + rate) - 1)
                        if strategy not in ("volatility", "rate_guard")
                        else None
                    ),
                    "forced_exit": i == end - 1,
                }
            )
            entry = None
    if entry:
        j, price, weight = entry
        trades.append(
            {
                "entry_date": str(frame.date.iloc[j]),
                "exit_date": str(frame.date.iloc[end - 1]),
                "entry_price": price,
                "exit_price": float(p.iloc[end - 1]),
                "net_return": (
                    float((p.iloc[end - 1] / price) * (1 - rate) / (1 + rate) - 1)
                    if strategy not in ("volatility", "rate_guard")
                    else None
                ),
                "forced_exit": True,
            }
        )
    result = metrics(returns, trades)
    if strategy in ("volatility", "rate_guard"):
        result["win_rate"] = None
        result["trade_count"] = len(trades)
    return {
        "fills": fills,
        "rate_alignment": rate_alignment,
        "metrics": result,
        "benchmark": metrics(benchmark),
        "curve": [
            {
                "date": str(frame.date.iloc[i]),
                "strategy": float(eq[k]),
                "benchmark": float(beq[k]),
                "drawdown": float(dd[k]),
                "exposure": float(holding_values[k]),
                "return": float(returns[k]),
            }
            for k, i in enumerate(range(start, end))
        ],
        "trades": trades,
        "turnover": float(sum(turn_values)),
        "cost_drag_sum": float(sum(cost_values)),
        "period": period,
        "start": str(frame.date.iloc[start]),
        "end": str(frame.date.iloc[end - 1]),
        "observations": len(returns),
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "latest_target": float(signals.iloc[-1]),
        "assumptions": [
            "Signal at t close; execution at t+1 close; first holding return at t+2.",
            "Long/cash, no leverage. Uninvested cash earns zero. Sharpe risk-free reference is zero.",
            "Both-side fees and slippage; final-close liquidation; proportional cost approximation.",
            "Development before 2023; validation in 2023; reserved test from 2024. Fixed parameters, no optimization. Repeated inspection compromises test independence.",
            "Current provider vintage. Revisions, survivorship and corporate-action adjustment bias may remain.",
            "Volatility and rate-aware rules rebalance daily. Per-trade win rate has no consistent definition and shows N/A.",
            "Rate-aware rule uses Yahoo ^IRX 13-week Treasury-bill yield proxy (percent), strictly before each signal date, carried at most seven days.",
            "Rate-aware exposure = trend-filtered 12% volatility-target weight / (1 + 5 × max(short yield,0)/100). Fixed educational coefficient, not an optimized rule or the federal funds rate.",
        ],
    }
