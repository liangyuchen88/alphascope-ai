import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
import data_service as service


def test_cached_failure_preserves_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "CACHE", tmp_path)
    original = {
        "rows": [{"date": "2024-01-01", "close": 100}],
        "retrieved_at": "2024-01-02T00:00:00Z",
        "provider": "fixture for unit tests only",
    }
    (tmp_path / "test.json").write_text(json.dumps(original))

    def fail():
        raise TimeoutError("offline")

    value = service.cached("test", fail, True)
    assert value["cache_status"] == "stale"
    assert value["retrieved_at"] == original["retrieved_at"]
    assert value["rows"] == original["rows"]
    assert "offline" in value["fetch_error"]


def test_unavailable_never_returns_synthetic_prices(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "CACHE", tmp_path)

    def fail():
        raise TimeoutError("offline")

    value = service.cached("missing", fail)
    assert value["status"] == "unavailable"
    assert "rows" not in value


@pytest.mark.parametrize("symbol", ["../../secret", "SPY?x=1", "", "aapl", "A" * 30])
def test_symbol_validation(symbol):
    with pytest.raises(ValueError):
        service.prices(symbol)
