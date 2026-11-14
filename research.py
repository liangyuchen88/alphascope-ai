"""Reproduce the dashboard's test-period research report from source-tagged caches."""

import argparse, concurrent.futures, json, sys
from pathlib import Path
from data_service import ASSETS, prices, now
from engine import STRATEGIES, backtest


def run(refresh=False, output="reports"):
    root = Path(__file__).parent / output
    root.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        data = dict(zip(ASSETS, pool.map(lambda s: prices(s, refresh), ASSETS)))
    rates = prices("^IRX", refresh)
    reports = []
    for symbol, d in data.items():
        for strategy in STRATEGIES:
            try:
                result = backtest(
                    d["rows"],
                    strategy,
                    period="test",
                    rate_rows=rates.get("rows") if strategy == "rate_guard" else None,
                )
                entry = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "start": result["start"],
                    "end": result["end"],
                    "metrics": result["metrics"],
                    "source_url": d["url"],
                    "source_sha256": d["sha256"],
                    "retrieved_at": d["retrieved_at"],
                }
                if strategy == "rate_guard":
                    entry["rate_source"] = {
                        k: v for k, v in rates.items() if k != "rows"
                    }
                if symbol in ("SPY", "GLD", "USO"):
                    result["source"] = {k: v for k, v in d.items() if k != "rows"}
                    if strategy == "rate_guard":
                        result["rate_source"] = {
                            k: v for k, v in rates.items() if k != "rows"
                        }
                    (root / (symbol + "-" + strategy + ".json")).write_text(
                        json.dumps(
                            result, ensure_ascii=False, indent=2, allow_nan=False
                        )
                    )
                reports.append(entry)
            except Exception as e:
                reports.append(
                    {"symbol": symbol, "strategy": strategy, "error": str(e)}
                )
        print(symbol, "done", flush=True)
    report = {
        "generated_at": now(),
        "description": "Fixed-parameter historical test-period research, not forward-validated recommendations. See README and METHODOLOGY.",
        "fee_bps": 5,
        "slippage_bps": 5,
        "results": reports,
    }
    (root / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    )
    errors = [r for r in reports if "error" in r]
    print(
        f"{len(reports)-len(errors)}/{len(reports)} backtests completed. Output: {root}"
    )
    return bool(errors)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--output", default="reports")
    a = p.parse_args()
    sys.exit(run(a.refresh, a.output))
