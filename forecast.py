"""Fixed ridge forecasts with label-aware walk-forward tests and held-out calibration."""

import concurrent.futures, hashlib, json
import numpy as np
import pandas as pd
from data_service import prices, ASSETS, now
from fx import reference_history, pair_rows

FEATURES = [
    "ret_1",
    "ret_5",
    "ret_20",
    "ret_63",
    "sma_gap",
    "vol_20",
    "vix_previous",
    "bill_yield_previous",
    "spy_return_previous",
]


def build_features(rows, external, horizon=5):
    if horizon not in (1, 5):
        raise ValueError("Forecast horizon must be 1 or 5 observation sessions")
    f = pd.DataFrame(rows)[["date", "close"]].copy()
    f["date"] = pd.to_datetime(f.date)
    f = f.sort_values("date").reset_index(drop=True)
    if (
        f.date.duplicated().any()
        or (f.close <= 0).any()
        or not np.isfinite(f.close).all()
    ):
        raise ValueError("Invalid forecast price history")
    p = f.close.astype(float)
    for k in (1, 5, 20, 63):
        f["ret_" + str(k)] = p.pct_change(k, fill_method=None)
    f["sma_gap"] = p / p.rolling(60).mean() - 1
    f["vol_20"] = p.pct_change(fill_method=None).rolling(20).std() * np.sqrt(252)
    for symbol, feature in [
        ("^VIX", "vix_previous"),
        ("^IRX", "bill_yield_previous"),
        ("SPY", "spy_return_previous"),
    ]:
        source = external.get(symbol, {}).get("rows", [])
        if not source:
            raise ValueError(symbol + " historical context unavailable")
        e = pd.DataFrame(source)[["date", "close"]]
        e["context_date"] = pd.to_datetime(e.date)
        e = e.sort_values("context_date")
        e[feature] = (
            e.close.pct_change(5, fill_method=None)
            if symbol == "SPY"
            else e.close / 100
        )
        e = e[["context_date", feature]].rename(
            columns={"context_date": feature + "_date"}
        )
        f = pd.merge_asof(
            f,
            e,
            left_on="date",
            right_on=feature + "_date",
            direction="backward",
            allow_exact_matches=False,
            tolerance=pd.Timedelta(days=7),
        )
    f["target"] = p.shift(-horizon) / p - 1
    f["target_date"] = f.date.shift(-horizon)
    return f


def ridge_predict(x, y, x0, alpha=10.0):
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (x - mean) / scale
    center = float(y.mean())
    coefficients = np.linalg.solve(
        z.T @ z + alpha * np.eye(x.shape[1]), z.T @ (y - center)
    )
    terms = ((x0 - mean) / scale) * coefficients
    return float(center + terms.sum()), center, terms


def run_forecast(frame, horizon=5, train_window=756, min_train=252):
    f = frame.reset_index(drop=True)
    x = f[FEATURES].to_numpy(dtype=float)
    y = f.target.to_numpy(dtype=float)
    valid = np.isfinite(x).all(axis=1)
    records = []

    def estimate(i):
        # A training label is usable only after its ending observation exists at origin i.
        usable = np.flatnonzero(
            valid & np.isfinite(y) & (f.target_date <= f.date.iloc[i]).to_numpy()
        )[-train_window:]
        if len(usable) < min_train:
            raise ValueError("Insufficient past training labels")
        pred, intercept, terms = ridge_predict(x[usable], y[usable], x[i])
        return pred, intercept, terms, usable

    candidates = np.flatnonzero(
        valid & np.isfinite(y) & (f.date >= pd.Timestamp("2023-01-01")).to_numpy()
    )
    # Non-overlapping targets within each period; all preceding known labels can train the model.
    last_origin = {"validation": -100, "test": -100}
    for i in candidates:
        if f.date.iloc[i] < pd.Timestamp("2024-01-01"):
            if f.target_date.iloc[i] >= pd.Timestamp("2024-01-01"):
                continue
            period = "validation"
        else:
            period = "test"
        if i - last_origin[period] < horizon:
            continue
        try:
            pred, _, _, train = estimate(i)
        except ValueError:
            continue
        last_origin[period] = i
        records.append(
            {
                "origin_date": f.date.iloc[i].strftime("%Y-%m-%d"),
                "target_date": f.target_date.iloc[i].strftime("%Y-%m-%d"),
                "prediction": pred,
                "actual": float(y[i]),
                "no_change_prediction": 0.0,
                "period": period,
                "training_count": len(train),
                "training_latest_label_date": f.target_date.iloc[train[-1]].strftime(
                    "%Y-%m-%d"
                ),
            }
        )
    calibration = [r for r in records if r["period"] == "validation"]
    test = [r for r in records if r["period"] == "test"]
    if len(calibration) < 30 or len(test) < 30:
        raise ValueError(
            "At least 30 validation and 30 out-of-sample observations are required"
        )
    residuals = np.array([r["actual"] - r["prediction"] for r in calibration])
    qlo, qhi = np.quantile(residuals, [0.1, 0.9])
    calibration_end = max(r["target_date"] for r in calibration)
    for r in test:
        r["lower"] = float(r["prediction"] + qlo)
        r["upper"] = float(r["prediction"] + qhi)
        r["calibration_latest_label_date"] = calibration_end
    actual = np.array([r["actual"] for r in test])
    predictions = np.array([r["prediction"] for r in test])
    rmse = float(np.sqrt(np.mean((actual - predictions) ** 2)))
    baseline = float(np.sqrt(np.mean(actual**2)))
    nonzero = abs(actual) > 1e-12
    last = len(f) - 1
    if not valid[last]:
        raise ValueError(
            "Latest forecast inputs are missing or too old; no forward forecast available"
        )
    pred, intercept, terms, train = estimate(last)
    price = float(f.close.iloc[last])
    if 1 + pred <= 0 or 1 + pred + qlo <= 0:
        raise ValueError("Model produced invalid nonpositive price estimates")
    external_dates = {
        name: f[name + "_date"].iloc[last].strftime("%Y-%m-%d")
        for name in FEATURES
        if name.endswith("previous")
    }
    return {
        "model": "Fixed ridge regression on horizon returns",
        "horizon_sessions": horizon,
        "alpha": 10.0,
        "training_window_max": train_window,
        "min_training_labels": min_train,
        "origin_date": f.date.iloc[last].strftime("%Y-%m-%d"),
        "last_observed_price": price,
        "forecast_return": pred,
        "forecast_price": price * (1 + pred),
        "lower_return": float(pred + qlo),
        "upper_return": float(pred + qhi),
        "lower_price": float(price * (1 + pred + qlo)),
        "upper_price": float(price * (1 + pred + qhi)),
        "interval_nominal_coverage": 0.8,
        "calibration_count": len(calibration),
        "calibration_latest_label_date": calibration_end,
        "external_observation_dates": external_dates,
        "training_count": len(train),
        "training_latest_label_date": f.target_date.iloc[train[-1]].strftime(
            "%Y-%m-%d"
        ),
        "intercept_contribution": intercept,
        "feature_contributions": [
            {
                "feature": name,
                "return_contribution": float(value),
                "latest_input": float(x[last, j]),
            }
            for j, (name, value) in enumerate(zip(FEATURES, terms))
        ],
        "metrics": {
            "test_count": len(test),
            "rmse": rmse,
            "baseline_rmse": baseline,
            "rmse_ratio": rmse / baseline if baseline > 1e-12 else None,
            "mae": float(np.mean(abs(actual - predictions))),
            "baseline_mae": float(np.mean(abs(actual))),
            "directional_accuracy": (
                float(
                    np.mean(np.sign(predictions[nonzero]) == np.sign(actual[nonzero]))
                )
                if nonzero.any()
                else None
            ),
            "interval_empirical_coverage": float(
                np.mean([(r["lower"] <= r["actual"] <= r["upper"]) for r in test])
            ),
        },
        "evidence_status": (
            "LOWER HISTORICAL TEST RMSE / NOT A FUTURE GUARANTEE"
            if rmse < baseline
            else "NO DEMONSTRATED EDGE OVER NO-CHANGE BENCHMARK"
        ),
        "validation": calibration,
        "test": test,
        "recent_history": [
            {"date": r["date"].strftime("%Y-%m-%d"), "close": float(r["close"])}
            for r in f.tail(126).to_dict("records")
        ],
        "assumptions": [
            "Targets are returns over the next 1 or 5 available observations; calendar dates are not promised. FX forecasts target ECB reference observations, not executable broker prices.",
            "Features: own 1/5/20/63-observation returns, 60-observation average gap, 20-return annualized volatility; strictly earlier VIX, US 13-week bill-yield proxy and SPY five-session return. External context is carried at most seven calendar days.",
            "All external observations precede the forecast origin date. This conservative lag avoids using the US close after the ECB reference observation on the same calendar day. It is not a complete point-in-time publication-vintage database.",
            "Ridge alpha 10, maximum 756 training rows, minimum 252; feature scaling is fit on the training slice only. Every training label ends no later than its forecast origin. No hyperparameter optimization.",
            "Validation origins/labels stay in 2023. Their signed residual 10th/90th percentiles define an illustrative nominal 80% interval. Test origins start in 2024 and are scored on known future labels. Rolling training may use prior test labels once observed.",
            "Test origins are separated by the forecast horizon to avoid overlapping target windows within the test period. Interval coverage is measured, not assumed. Calibration can fail under regime changes.",
            "Current-vintage adjusted prices/reference rates can be revised. Repeated inspection of historical tests weakens independence; this is not preregistered or independent forward validation.",
            "Current news, political outcomes and FRED snapshots are excluded from numerical features because point-in-time historical coverage is not available. Transmission Map remains a separately labelled hypothesis framework.",
            "Feature contributions are model arithmetic, not causal effects. Directional accuracy is scored only on nonzero actual returns; the no-change forecast has no directional prediction.",
            "Statistical forecast evaluation is not a trading P&L backtest. No leverage, costs, funding, execution or tradable strategy is inferred. Forecast trading profitability has not been validated.",
        ],
    }


def forecast_request(payload):
    kind = payload.get("kind", "fx")
    symbol = payload.get("symbol", "EUR/USD")
    horizon = payload.get("horizon", 5)
    if type(horizon) is not int or horizon not in (1, 5):
        raise ValueError("Horizon must be 1 or 5")
    if kind == "fx":
        source = reference_history()
        rows = pair_rows(source, symbol)
    elif kind == "asset" and symbol in ASSETS:
        source = prices(symbol)
        rows = source.get("rows", [])
    else:
        raise ValueError("Unsupported forecast instrument")
    if len(rows) < 756:
        raise ValueError("At least 756 real source observations required")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        external = dict(
            zip(("^VIX", "^IRX", "SPY"), pool.map(prices, ("^VIX", "^IRX", "SPY")))
        )
    frame = build_features(rows, external, horizon)
    result = run_forecast(frame, horizon)
    age = (
        pd.Timestamp.now(tz="UTC").date() - pd.Timestamp(result["origin_date"]).date()
    ).days
    if age < 0:
        raise ValueError(
            "Future-dated source observations cannot produce a current forecast"
        )
    stale = (
        age > 5
        or source.get("cache_status") == "stale"
        or any(d.get("cache_status") == "stale" for d in external.values())
    )
    result.update(
        symbol=symbol,
        kind=kind,
        source={k: v for k, v in source.items() if k != "rows"},
        context_sources=[
            {k: v for k, v in d.items() if k != "rows"} for d in external.values()
        ],
        generated_at=now(),
        stale=stale,
        forecast_status=(
            "STALE INPUTS / HISTORICAL MODEL OUTPUT ONLY"
            if stale
            else "RESEARCH ESTIMATE / NOT A TRADE INSTRUCTION"
        ),
    )
    result["dataset_sha256"] = hashlib.sha256(
        json.dumps(
            {
                "rows": rows,
                "external_hashes": {s: d.get("sha256") for s, d in external.items()},
                "horizon": horizon,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return result
