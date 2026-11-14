import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
import pytest
from risk import evaluate_market_risk, evaluate_replay_risk, concentration


def market():
    return {
        "generated_at": "2026-11-14T12:00:00Z",
        "assets": [
            {
                "symbol": "SPY",
                "last": 101.0,
                "sma60": 100.0,
                "volatility": 0.15,
                "change": 0.001,
                "date": "2026-11-13",
                "provider": "UNIT TEST fixture",
                "url": "https://example.test/spy",
                "retrieved_at": "2026-11-14T10:00:00Z",
            }
        ],
        "vix": {
            "rows": [{"date": "2026-11-13", "close": 19.0}],
            "provider": "Cboe test fixture",
            "url": "https://example.test/vix",
        },
        "macro": {},
    }


def test_no_trigger_does_not_claim_safety():
    r = evaluate_market_risk(market())
    assert r["status"] == "no_trigger"
    assert "safe" in r["notice"]  # Explicitly disclaims that no trigger means safe.
    assert r["coverage"]["portfolio"].startswith("No portfolio supplied")


@pytest.mark.parametrize(
    "value,severity", [(20, "warning"), (29.99, "warning"), (30, "critical")]
)
def test_vix_threshold_boundaries_are_explainable(value, severity):
    data = market()
    data["vix"]["rows"][0]["close"] = value
    r = evaluate_market_risk(data)
    a = next(a for a in r["alerts"] if a["id"] == "vix")
    assert a["severity"] == severity and a["value"] == value
    assert a["observed_date"] == "2026-11-13"
    assert a["sources"][0]["provider"] == "Cboe test fixture"
    assert not a["automatic_action"]


def test_stale_high_vix_suppresses_current_stress_classification():
    data = market()
    data["vix"]["rows"][0] = {"date": "2020-03-16", "close": 80.0}
    r = evaluate_market_risk(data)
    assert any(a["id"] == "data_VIX" for a in r["alerts"])
    assert not any(a["id"] == "vix" for a in r["alerts"])
    assert r["status"] == "incomplete"


def test_failed_refresh_and_missing_data_never_get_all_clear():
    data = market()
    data["assets"][0]["cache_status"] = "stale"
    data["vix"]["rows"] = []
    r = evaluate_market_risk(data)
    assert r["status"] == "incomplete"
    assert r["counts"]["unavailable"] == 2


def test_future_observation_is_not_current_evidence():
    data = market()
    data["vix"]["rows"][0] = {"date": "2026-11-15", "close": 99.0}
    r = evaluate_market_risk(data)
    assert not r["coverage"]["vix"]
    assert not any(a["id"] == "vix" for a in r["alerts"])


def test_etf_concentration_strict_boundaries_and_floating_tolerance():
    assert not concentration({"SPY": 0.6 + 1e-15}, "2020-01-01", [], "targets")
    assert (
        concentration({"SPY": 0.8}, "2020-01-01", [], "targets")[0]["severity"]
        == "warning"
    )
    assert (
        concentration({"SPY": 0.81}, "2020-01-01", [], "targets")[0]["severity"]
        == "critical"
    )


def historical():
    return {
        "as_of": "2020-03-16",
        "vix": 80.0,
        "spy_sma60": 100.0,
        "spy_volatility": 0.6,
        "observations": [
            {"date": "2020-03-13", "SPY": 100.0},
            {"date": "2020-03-16", "SPY": 90.0},
        ],
        "sources": [
            {"symbol": "SPY", "provider": "Historical fixture"},
            {"symbol": "^VIX", "provider": "Cboe fixture"},
        ],
        "paths": {
            "player": {"weights": {"SPY": 0.9}, "metrics": {"max_drawdown": -0.22}}
        },
        "budget": 0.2,
    }


def test_historical_alerts_use_replay_date_not_today():
    r = evaluate_replay_risk(historical())
    assert r["context"].startswith("HISTORICAL REPLAY") and r["as_of"] == "2020-03-16"
    assert any(a["id"] == "vix" and a["severity"] == "critical" for a in r["alerts"])
    assert not any(a["id"].startswith("data_") for a in r["alerts"])
    assert all(a["observed_date"] == "2020-03-16" for a in r["alerts"])


@pytest.mark.parametrize(
    "mdd,severity", [(-0.16, "warning"), (-0.20, "critical"), (-0.22, "critical")]
)
def test_drawdown_budget_warning_and_breach(mdd, severity):
    data = historical()
    data["paths"]["player"]["metrics"]["max_drawdown"] = mdd
    r = evaluate_replay_risk(data)
    a = next(a for a in r["alerts"] if a["id"] == "drawdown")
    assert a["severity"] == severity
    assert a["value"] == pytest.approx(abs(mdd) / 0.2)


def test_alert_evaluation_never_mutates_positions_or_inputs():
    data = historical()
    before = copy.deepcopy(data)
    evaluate_replay_risk(data)
    assert data == before


def test_missing_indicator_coverage_is_reported():
    data = market()
    data["assets"][0]["volatility"] = None
    r = evaluate_market_risk(data)
    assert r["status"] == "incomplete"
    assert any(a["id"] == "indicator_coverage" for a in r["alerts"])
