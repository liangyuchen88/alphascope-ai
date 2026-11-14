import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from global_markets import rank_frame


def test_ranking_uses_september_not_august_and_excludes_totals():
    f = pd.DataFrame(
        {
            "Exchange Name": ["Total global"] + [f"Exchange {i}" for i in range(12)],
            "Aug'26": [999999] + list(range(1, 13)),
            "Sept'26": [999999] + list(range(12, 0, -1)),
        }
    )
    r = rank_frame(f)
    assert r["column"] == "Sept'26"
    assert r["observation_date"] == "2026-09-30"
    assert r["rows"][0]["exchange"] == "Exchange 0"
    assert len(r["rows"]) == 10
    assert r["reporting_exchanges"] == 12


def test_ranking_rejects_missing_month_or_incomplete_table():
    with pytest.raises(ValueError):
        rank_frame(pd.DataFrame({"Exchange Name": ["x"], "foo": [1]}))
    with pytest.raises(ValueError):
        rank_frame(pd.DataFrame({"Exchange Name": ["x"], "Sept'26": [1]}))
