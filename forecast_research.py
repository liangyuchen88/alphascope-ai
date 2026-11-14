"""Reproduce all supported FX/market forecast evaluations from source-tagged history."""

import json
from pathlib import Path
from data_service import now
from fx import PAIRS
from forecast import forecast_request

ASSET_MODELS = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GLD", "USO", "TLT")


def main():
    root = Path(__file__).parent / "reports"
    results = []
    for kind, symbol in [("fx", s) for s in PAIRS] + [
        ("asset", s) for s in ASSET_MODELS
    ]:
        for horizon in (1, 5):
            try:
                d = forecast_request(
                    {"kind": kind, "symbol": symbol, "horizon": horizon}
                )
                results.append(
                    {
                        k: d[k]
                        for k in (
                            "kind",
                            "symbol",
                            "horizon_sessions",
                            "origin_date",
                            "metrics",
                            "evidence_status",
                            "forecast_status",
                            "dataset_sha256",
                            "forecast_return",
                            "lower_return",
                            "upper_return",
                        )
                    }
                )
                if (symbol, horizon) in [
                    ("EUR/USD", 1),
                    ("EUR/USD", 5),
                    ("SPY", 5),
                    ("USO", 5),
                ]:
                    (
                        root / f'forecast-{symbol.replace("/","-")}-{horizon}.json'
                    ).write_text(json.dumps(d, ensure_ascii=False, indent=2))
                print(
                    kind,
                    symbol,
                    horizon,
                    d["metrics"]["test_count"],
                    d["evidence_status"],
                    flush=True,
                )
            except Exception as e:
                results.append(
                    {
                        "kind": kind,
                        "symbol": symbol,
                        "horizon_sessions": horizon,
                        "error": str(e),
                    }
                )
                print("ERROR", kind, symbol, horizon, str(e), flush=True)
    (root / "forecast-summary.json").write_text(
        json.dumps(
            {
                "generated_at": now(),
                "notice": "Statistical walk-forward forecast evaluation; not validated tradable P&L or guaranteed future accuracy.",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    errors = sum("error" in r for r in results)
    print(f"{len(results)-errors}/{len(results)} forecast evaluations completed")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
