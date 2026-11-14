import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from forecast import build_features, run_forecast, ridge_predict, FEATURES


def fixture():
    dates = pd.bdate_range("2019-01-01", "2026-11-13")
    rng = np.random.default_rng(81)
    prices = np.exp(np.cumsum(rng.normal(0, 0.003, len(dates))))
    rows = [
        {"date": d.strftime("%Y-%m-%d"), "close": float(p)}
        for d, p in zip(dates, prices)
    ]
    external = {
        s: {
            "rows": [
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "close": (
                        20.0 if s == "^VIX" else 3.0 if s == "^IRX" else 100 + i * 0.01
                    ),
                }
                for i, d in enumerate(dates)
            ]
        }
        for s in ["^VIX", "^IRX", "SPY"]
    }
    return rows, external


def test_external_features_are_strictly_prior_observations():
    rows, e = fixture()
    f = build_features(rows, e)
    for name in ["vix_previous", "bill_yield_previous", "spy_return_previous"]:
        valid = f[name + "_date"].notna()
        assert (f.loc[valid, name + "_date"] < f.loc[valid, "date"]).all()


def test_training_labels_and_calibration_do_not_leak_future():
    rows, e = fixture()
    r = run_forecast(build_features(rows, e), 5)
    assert all(
        x["training_latest_label_date"] <= x["origin_date"]
        for x in r["test"] + r["validation"]
    )
    assert all(x["calibration_latest_label_date"] < x["origin_date"] for x in r["test"])
    assert r["calibration_latest_label_date"] < "2024-01-01"
    assert r["training_latest_label_date"] <= r["origin_date"]
    assert r["metrics"]["test_count"] > 30


def test_future_mutation_does_not_change_earlier_predictions():
    rows, e = fixture()
    f = build_features(rows, e)
    a = run_forecast(f, 5)
    mutated = [
        dict(r, close=r["close"] * 1.5) if r["date"] >= "2025-06-01" else dict(r)
        for r in rows
    ]
    b = run_forecast(build_features(mutated, e), 5)
    ap = {
        r["origin_date"]: r["prediction"]
        for r in a["test"]
        if r["origin_date"] < "2025-06-01"
    }
    bp = {
        r["origin_date"]: r["prediction"]
        for r in b["test"]
        if r["origin_date"] < "2025-06-01"
    }
    assert ap == bp


def test_forecast_contributions_add_up_and_intervals_are_ordered():
    rows, e = fixture()
    r = run_forecast(build_features(rows, e), 5)
    assert r["forecast_return"] == pytest.approx(
        r["intercept_contribution"]
        + sum(x["return_contribution"] for x in r["feature_contributions"])
    )
    assert r["lower_price"] < r["upper_price"]
    assert 0 <= r["metrics"]["interval_empirical_coverage"] <= 1


def test_ridge_scaling_handles_constant_features():
    pred, intercept, terms = ridge_predict(
        np.ones((300, 2)), np.full(300, 0.01), np.ones(2)
    )
    assert pred == pytest.approx(0.01) and np.isfinite(terms).all()


def test_missing_context_and_short_history_are_rejected():
    rows, e = fixture()
    e["^VIX"]["rows"] = []
    with pytest.raises(ValueError):
        build_features(rows, e)
    rows, e = fixture()
    with pytest.raises(ValueError):
        run_forecast(build_features(rows[:100], e), 5)
