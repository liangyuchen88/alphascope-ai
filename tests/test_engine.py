import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from engine import indicators, targets, backtest, metrics


def rows(prices):
    return [
        {"date": d.strftime("%Y-%m-%d"), "close": float(p)}
        for d, p in zip(pd.bdate_range("2024-01-01", periods=len(prices)), prices)
    ]


def test_rsi_rising_falling_flat():
    assert indicators(np.arange(1, 101)).rsi.iloc[-1] == 100
    assert indicators(np.arange(100, 0, -1)).rsi.iloc[-1] == 0
    assert indicators([10.0] * 100).rsi.iloc[-1] == 50


def test_warmup():
    s = targets(np.arange(1, 401), "trend")
    assert not s.iloc[:59].any()
    assert s.iloc[59] == 1
    assert not targets(np.arange(1, 401), "momentum").iloc[:63].any()


def test_next_close_execution_no_same_day_profit():
    p = np.r_[np.full(100, 100.0), 200.0, np.full(299, 200.0)]
    result = backtest(rows(p), fee_bps=0, slippage_bps=0, period="all")
    curve = result["curve"]
    jump = next(i for i, r in enumerate(curve) if r["date"] == rows(p)[100]["date"])
    assert curve[jump]["return"] == 0
    assert curve[jump + 1]["exposure"] == 0
    assert curve[jump + 2]["exposure"] == 1
    assert result["metrics"]["total_return"] == pytest.approx(0)


def test_prefix_invariance_no_future_signal_leak():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.01, 500)))
    for strategy in ["trend", "momentum", "reversion", "volatility"]:
        np.testing.assert_allclose(
            targets(p, strategy).iloc[:300], targets(p[:300], strategy)
        )


def test_costs_reduce_wealth_and_benchmark():
    p = np.linspace(100, 200, 500)
    free = backtest(rows(p), fee_bps=0, slippage_bps=0, period="all")
    cost = backtest(rows(p), fee_bps=10, slippage_bps=10, period="all")
    assert cost["metrics"]["total_return"] < free["metrics"]["total_return"]
    assert cost["benchmark"]["total_return"] < free["benchmark"]["total_return"]
    assert cost["turnover"] == pytest.approx(1 + 1 / 1.002)
    assert cost["cost_drag_sum"] == pytest.approx(0.002 * (1 + 1 / 1.002))
    price_rows = rows(p)
    entry = cost["trades"][0]["entry_price"]
    exit = cost["trades"][0]["exit_price"]
    assert cost["metrics"]["total_return"] == pytest.approx(
        exit / entry * 0.998 / 1.002 - 1
    )
    assert cost["trades"][0]["net_return"] == pytest.approx(
        cost["metrics"]["total_return"]
    )
    assert cost["trades"][-1]["forced_exit"]


def test_metrics_drawdown_includes_initial_cash():
    m = metrics([-0.1, 0.05])
    assert m["max_drawdown"] == pytest.approx(-0.1)
    assert m["total_return"] == pytest.approx(-0.055)
    assert m["cagr"] is None
    assert m["sharpe"] is None


def test_known_sharpe():
    r = np.array([0.01, -0.005] * 150)
    m = metrics(r)
    assert m["sharpe"] == pytest.approx(r.mean() / r.std(ddof=1) * np.sqrt(252))


def test_reproducibility():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(42).normal(0.0002, 0.012, 600)))
    assert backtest(rows(p)) == backtest(rows(p))


def test_vol_target_bounded_no_leverage():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(6).normal(0.001, 0.02, 500)))
    s = targets(p, "volatility")
    assert s.between(0, 1).all()
    result = backtest(rows(p), "volatility", period="all")
    assert result["metrics"]["win_rate"] is None


def test_fixed_calendar_splits():
    data = [
        {"date": d.strftime("%Y-%m-%d"), "close": 100 + i * 0.02}
        for i, d in enumerate(pd.bdate_range("2020-01-01", "2026-01-01"))
    ]
    dev = backtest(data, period="development")
    val = backtest(data, period="validation")
    test = backtest(data, period="test")
    assert dev["end"] < "2023-01-01"
    assert "2023-01-01" <= val["start"] <= val["end"] < "2024-01-01"
    assert test["start"] >= "2024-01-01"
    assert dev["curve"][0]["exposure"] == 0


@pytest.mark.parametrize(
    "data",
    [
        rows([1.0] * 20),
        rows([0.0] * 300),
        rows([-1.0] * 300),
        rows([float("nan")] * 300),
    ],
)
def test_reject_invalid_data(data):
    with pytest.raises(ValueError):
        backtest(data)


def test_reject_duplicate_dates():
    data = rows([1.0] * 300)
    data[1]["date"] = data[0]["date"]
    with pytest.raises(ValueError):
        backtest(data)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"strategy": "magic"},
        {"fee_bps": -1},
        {"slippage_bps": 101},
        {"period": "magic"},
    ],
)
def test_reject_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        backtest(rows(np.linspace(1, 2, 300)), **kwargs)


def test_rate_guard_responds_to_rates_and_bounds_exposure():
    prices = np.linspace(100, 200, 500)
    low = targets(prices, "rate_guard", np.full(500, 1.0))
    high = targets(prices, "rate_guard", np.full(500, 6.0))
    assert high.iloc[-1] < low.iloc[-1]
    assert high.between(0, 1).all()


def test_rate_alignment_strictly_previous_day_and_future_invariant():
    p = np.linspace(100, 200, 500)
    data = rows(p)
    rates = [{"date": r["date"], "close": 3.0} for r in data]
    a = backtest(data, "rate_guard", period="all", rate_rows=rates)
    assert all(
        r["rate_date"] < r["date"] for r in a["rate_alignment"] if r["rate_date"]
    )
    changed = rates[:]
    changed[-1] = {"date": rates[-1]["date"], "close": 100.0}
    b = backtest(data, "rate_guard", period="all", rate_rows=changed)
    assert (
        a == b
    )  # Same-day rate cannot influence today's signal or historical returns.
    assert a["metrics"]["win_rate"] is None


def test_rate_guard_requires_coverage():
    with pytest.raises(ValueError):
        backtest(rows(np.linspace(100, 200, 500)), "rate_guard")
    with pytest.raises(ValueError):
        backtest(
            rows(np.linspace(100, 200, 500)),
            "rate_guard",
            rate_rows=[{"date": "2020-01-01", "close": 4.0}],
        )


def test_fractional_ledger_matches_independent_zero_cost_calculation():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(19).normal(0.001, 0.02, 500)))
    result = backtest(rows(p), "volatility", 0, 0, period="all")
    signal = targets(p, "volatility")
    expected = 1.0
    for i in range(63, len(p)):
        previous_weight = 0 if i == 63 else signal.iloc[i - 2]
        expected *= 1 + previous_weight * (p[i] / p[i - 1] - 1)
    assert result["curve"][-1]["strategy"] == pytest.approx(expected)
