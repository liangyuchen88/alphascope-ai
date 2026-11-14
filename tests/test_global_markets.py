import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from global_markets import MARKETS, align_indices


def test_watchlist_covers_ten_distinct_major_markets():
    assert len(MARKETS) == 10
    assert len({m["index_symbol"] for m in MARKETS}) == 10
    assert {"United States", "United Kingdom", "Japan", "China", "Hong Kong"} <= {
        m["region"] for m in MARKETS
    }


def test_comparison_uses_exact_common_dates_and_rebases_to_100():
    histories = {
        "A": [
            {"date": "2026-01-01", "close": 10},
            {"date": "2026-01-02", "close": 20},
            {"date": "2026-01-03", "close": 22},
        ],
        "B": [
            {"date": "2026-01-02", "close": 100},
            {"date": "2026-01-03", "close": 90},
        ],
    }
    rows = align_indices(histories)
    assert len(rows) == 2
    assert rows[0] == {"date": "2026-01-02", "A": 100, "B": 100}
    assert rows[1]["A"] == pytest.approx(110)
    assert rows[1]["B"] == pytest.approx(90)


def test_missing_history_is_not_fabricated_and_short_windows_are_empty():
    assert align_indices({"A": [], "B": []}) == []
    assert align_indices({"A": [{"date": "2026-01-01", "close": 10}]}) == []
    rows = align_indices(
        {
            "A": [
                {"date": "2026-01-01", "close": 10},
                {"date": "2026-01-02", "close": 11},
            ],
            "B": [],
        }
    )
    assert "B" not in rows[0]
