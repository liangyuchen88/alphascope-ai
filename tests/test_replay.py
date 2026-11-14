import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
import numpy as np
import pandas as pd
import pytest
from replay import make_session, snapshot, advance, rebalance, validate_weights, SYMBOLS


def data():
    dates = pd.bdate_range("2019-01-01", "2020-05-15")
    out = {}
    for s in (*SYMBOLS, "^VIX"):
        rows = [
            {"date": d.strftime("%Y-%m-%d"), "close": 100.0 if s != "^VIX" else 20.0}
            for d in dates
        ]
        out[s] = {
            "symbol": s,
            "rows": rows,
            "provider": "Synthetic constant UNIT TEST fixture; never a market observation",
        }
    return out


def test_start_response_withholds_future_prices_news_and_curves():
    s = make_session("2020-storm", datasets=data())
    first = snapshot(s)
    assert first["as_of"] == "2020-02-19"
    assert all(
        r["date"] <= first["as_of"] for r in first["observations"] + first["curve"]
    )
    assert first["historical_release"] is None
    advance(s, action="hold", expected_turn=0)
    assert len(first["curve"]) == 1  # Returned snapshots never mutate with later turns.


def test_user_execution_is_next_session_and_charges_real_costs():
    s = make_session("2020-storm", weights={"SPY": 1}, datasets=data())
    result = advance(s, action="hold", expected_turn=0)
    fills = result["paths"]["player"]["fills"]
    assert fills[0]["date"] > "2020-02-19"
    assert fills[0]["decision_date"] == "2020-02-19"
    assert result["paths"]["player"]["nav"] == pytest.approx(100000 / 1.001)
    assert result["paths"]["player"]["cost_usd"] == pytest.approx(
        100000 - 100000 / 1.001
    )
    assert result["paths"]["player"]["nav"] == pytest.approx(
        result["paths"]["hold"]["nav"]
    )


def test_rebalance_pays_sell_and_buy_and_preserves_cash():
    cash, units, cost, signed = rebalance(
        0, np.array([1.0, 0.0]), np.array([100.0, 100.0]), [0.0, 1.0], 0.001
    )
    assert signed[0] < 0 and signed[1] > 0
    assert cash >= -1e-9
    assert cost == pytest.approx((100 + 100 * 0.999 / 1.001) * 0.001)
    assert cash + sum(units * 100) + cost == pytest.approx(100)


def test_cannot_profit_from_jump_before_execution():
    source = data()
    for r in source["SPY"]["rows"]:
        if r["date"] >= "2020-02-20":
            r["close"] = 200.0
    s = make_session("2020-storm", weights={"SPY": 1}, datasets=source)
    result = advance(s, action="hold", expected_turn=0)
    assert result["paths"]["player"]["nav"] == pytest.approx(100000 / 1.001)


def test_hold_causes_no_unrequested_rebalance():
    s = make_session("2020-storm", datasets=data())
    a = advance(s, action="hold", expected_turn=0)
    b = advance(s, action="hold", expected_turn=1)
    assert a["paths"]["player"]["fills"] == b["paths"]["player"]["fills"]


def test_duplicate_turn_is_rejected_before_mutation():
    s = make_session("2020-storm", datasets=data())
    advance(s, expected_turn=0)
    before = snapshot(s)
    with pytest.raises(ValueError):
        advance(s, expected_turn=0)
    assert snapshot(s) == before


def test_full_run_liquidates_and_exposes_only_published_history():
    s = make_session("2020-storm", weights={"SPY": 1}, datasets=data())
    while not s["complete"]:
        x = advance(s, expected_turn=s["turn"])
        assert all(r["date"] <= x["as_of"] for r in x["observations"] + x["curve"])
        if x["historical_release"]:
            assert x["historical_release"]["published_at"][:10] <= x["as_of"]
    assert x["as_of"] == "2020-05-15"
    assert x["paths"]["player"]["cash_weight"] == pytest.approx(1.0)
    assert x["paths"]["player"]["nav"] == pytest.approx(100000 * 0.999 / 1.001)
    assert x["paths"]["player"]["fills"][-1]["terminal_liquidation"]
    assert x["paths"]["player"]["metrics"]["trade_count"] is None
    with pytest.raises(ValueError):
        advance(s, expected_turn=s["turn"])


@pytest.mark.parametrize(
    "weights",
    [{"VIX": 1}, {"SPY": -1}, {"SPY": 0.9, "GLD": 0.9}, {"SPY": float("nan")}],
)
def test_invalid_allocations_are_rejected(weights):
    with pytest.raises(ValueError):
        validate_weights(weights)


def test_missing_source_never_uses_fake_market_history():
    source = data()
    source["GLD"]["rows"] = []
    with pytest.raises(ValueError):
        make_session("2020-storm", datasets=source)


def test_future_data_cannot_change_revealed_prefix():
    one = data()
    two = copy.deepcopy(one)
    for r in two["SPY"]["rows"]:
        if r["date"] > "2020-03-10":
            r["close"] *= 2
    a = make_session("2020-storm", datasets=one)
    b = make_session("2020-storm", datasets=two)
    xa = advance(a, expected_turn=0)
    xb = advance(b, expected_turn=0)
    assert xa == xb or (
        xa["curve"] == xb["curve"]
        and xa["observations"] == xb["observations"]
        and xa["paths"] == xb["paths"]
    )


def test_budget_ratio_can_exceed_100_percent_without_automatic_stop():
    source = data()
    for r in source["SPY"]["rows"]:
        if r["date"] >= "2020-02-28":
            r["close"] = 50.0
    s = make_session("2020-storm", weights={"SPY": 1}, budget=0.2, datasets=source)
    x = advance(s, expected_turn=0)
    assert x["budget_breached"]
    assert x["budget_used"] > 2
    assert x["budget_used"] == pytest.approx(
        abs(x["paths"]["player"]["metrics"]["max_drawdown"]) / 0.2
    )
    assert x["paths"]["player"]["weights"]["SPY"] == pytest.approx(1.0)
