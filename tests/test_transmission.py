import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from transmission import transmission_map, MAP_EVENTS


def data(end="2026-11-13"):
    dates = pd.bdate_range("2026-09-01", end)
    rows = [
        {"date": d.strftime("%Y-%m-%d"), "close": 100 + i * 0.1}
        for i, d in enumerate(dates)
    ]
    return {
        s: {
            "symbol": s,
            "rows": rows,
            "provider": "Synthetic UNIT TEST fixture; not market observations",
        }
        for s in ["SPY", "GLD", "USO", "TLT", "XLK", "^VIX"]
    }


def test_graph_types_and_arrows_never_claim_causality():
    x = transmission_map(datasets=data())
    assert {n["kind"] for n in x["nodes"]} == {
        "fact",
        "hypothesis",
        "observation",
        "user_input",
    }
    assert not x["causal_effects_estimated"] and not x["portfolio_forecast_available"]
    ids = {n["id"] for n in x["nodes"]}
    assert all(
        e["from"] in ids and e["to"] in ids and not e["estimated"] for e in x["edges"]
    )
    assert all(n["counter"] for n in x["nodes"])


def test_partial_window_and_source_provenance_are_preserved():
    x = transmission_map(datasets=data())
    spy = next(o for o in x["observations"] if o["symbol"] == "SPY")
    assert not spy["complete"] and spy["available_post_sessions"] < 20
    assert spy["summary"]["end_date"] == "2026-11-13"
    assert spy["sources"][0]["provider"].startswith("Synthetic UNIT TEST")


def test_missing_sector_never_generates_observations():
    x = transmission_map(datasets=data())
    missing = next(o for o in x["observations"] if o["symbol"] == "XLF")
    assert missing["summary"] is None and "error" in missing
    assert len(x["observations"]) == 15


def test_allocation_changes_do_not_change_historical_evidence():
    a = transmission_map(weights={"SPY": 1}, datasets=data())
    b = transmission_map(weights={"GLD": 1}, datasets=data())
    assert a["observations"] == b["observations"]
    assert a["exposure"] != b["exposure"]
    assert sum(e["weight"] for e in a["exposure"]) + a["cash_weight"] == pytest.approx(
        1
    )


def test_fact_records_have_primary_sources_and_dates():
    assert all(
        v["source"].startswith(
            ("https://www.fec.gov/", "https://www.federalreserve.gov/")
        )
        for v in MAP_EVENTS.values()
    )
    assert MAP_EVENTS["2022-rate-hike"]["published_at"] == "2022-03-16T14:00:00-04:00"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_key": "fiction"},
        {"window": 1},
        {"window": True},
        {"weights": {"SPY": 2}},
        {"weights": {"FAKE": 1}},
    ],
)
def test_invalid_requests_are_rejected(kwargs):
    with pytest.raises(ValueError):
        transmission_map(datasets=data(), **kwargs)
