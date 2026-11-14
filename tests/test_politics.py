import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from politics import event_study


def sample():
    return [
        {"date": d.strftime("%Y-%m-%d"), "close": 100.0 + i}
        for i, d in enumerate(pd.bdate_range("2022-10-01", periods=80))
    ]


def test_event_baseline_and_vix_units():
    a = sample()
    v = [{"date": r["date"], "close": 20 + i * 0.1} for i, r in enumerate(a)]
    result = event_study(a, a, v, "2022-11-08", 20)
    assert result["baseline_date"] == "2022-11-07"
    assert next(r for r in result["curve"] if r["session"] == -1)["asset"] == 0
    assert result["summary"]["excess_return"] == 0
    assert result["summary"]["vix_change_points"] == pytest.approx(2.1)
    assert result["complete"]


def test_incomplete_event_window_is_labelled():
    a = sample()[:30]
    result = event_study(a, a, None, "2022-11-08", 20)
    assert not result["complete"]
    assert result["summary"]["vix_change_points"] is None


def test_future_event_has_no_manufactured_returns():
    with pytest.raises(ValueError):
        event_study(sample(), sample(), None, "2030-01-01")


def test_no_pre_event_baseline():
    with pytest.raises(ValueError):
        event_study(sample(), sample(), None, "2022-01-01")
