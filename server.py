import argparse, json, mimetypes, os, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from data_service import prices, summary, overview, macro, news, ASSETS
from engine import backtest, indicators
from politics import political_news, study, EVENTS
from global_markets import world_view
from replay import start_game, advance_game, validate_weights
from risk import evaluate_market_risk
from transmission import transmission_map

ROOT = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("A JSON request of at most 16 KiB is required.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            path = urlparse(self.path).path
            if path == "/api/transmission":
                return self.send_json(
                    transmission_map(
                        payload.get("event", "2026-midterms"),
                        payload.get("weights"),
                        payload.get("window", 20),
                    )
                )
            if path == "/api/risk/evaluate":
                weights = validate_weights(payload.get("weights", {}))
                return self.send_json(
                    evaluate_market_risk(overview(), allocation=weights)
                )
            if path == "/api/replay/start":
                return self.send_json(start_game(payload))
            if path == "/api/replay/advance":
                return self.send_json(advance_game(payload))
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, TypeError, KeyError) as e:
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            return self.send_json({"error": str(e)}, 500)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        get = lambda k, d=None: q.get(k, [d])[0]
        try:
            if u.path == "/api/transmission":
                return self.send_json(
                    transmission_map(
                        get("event", "2026-midterms"), window=int(get("window", "20"))
                    )
                )
            if u.path == "/api/risk":
                return self.send_json(overview()["risk"])
            if u.path == "/api/global-markets":
                return self.send_json(world_view())
            if u.path == "/api/politics":
                return self.send_json({"news": political_news(), "events": EVENTS})
            if u.path == "/api/event-study":
                return self.send_json(
                    study(
                        get("event", "2026-midterms"),
                        get("symbol", "SPY").upper(),
                        int(get("window", "20")),
                    )
                )
            if u.path == "/api/health":
                return self.send_json({"status": "ok"})
            if u.path == "/api/overview":
                return self.send_json(overview())
            if u.path == "/api/asset":
                d = prices(get("symbol", "SPY").upper(), get("refresh") == "1")
                if "rows" not in d:
                    return self.send_json(d, 503)
                x = indicators([r["close"] for r in d["rows"]])
                rows = []
                for i, r in enumerate(d["rows"]):
                    rows.append(
                        r
                        | {
                            k: (
                                None
                                if __import__("pandas").isna(x[k].iloc[i])
                                else float(x[k].iloc[i])
                            )
                            for k in ["sma20", "sma60", "rsi", "volatility", "momentum"]
                        }
                    )
                return self.send_json(d | {"rows": rows, "summary": summary(d)})
            if u.path == "/api/backtest":
                symbol = get("symbol", "SPY").upper()
                if symbol.startswith("^"):
                    raise ValueError(
                        "Yield and volatility indices are research indicators, not investable backtest assets."
                    )
                d = prices(symbol)
                if d.get("instrument_type") == "INDEX":
                    raise ValueError(
                        "An index level is not an investable total-return backtest asset."
                    )
                if "rows" not in d:
                    return self.send_json(d, 503)
                rates = prices("^IRX") if get("strategy") == "rate_guard" else None
                result = backtest(
                    d["rows"],
                    get("strategy", "trend"),
                    float(get("fee", "5")),
                    float(get("slippage", "5")),
                    get("period", "test"),
                    rate_rows=rates.get("rows") if rates else None,
                )
                if rates:
                    result["rate_source"] = {
                        k: v for k, v in rates.items() if k != "rows"
                    }
                return self.send_json(
                    result
                    | {
                        "source": {k: v for k, v in d.items() if k != "rows"},
                        "symbol": symbol,
                        "strategy": get("strategy", "trend"),
                    }
                )
            if u.path == "/api/news":
                return self.send_json(news())
            if u.path == "/api/macro":
                return self.send_json(macro())
            if u.path == "/api/universe":
                return self.send_json(ASSETS)
            path = (
                ROOT
                / "static"
                / ("index.html" if u.path == "/" else u.path.lstrip("/"))
            )
            if (
                not path.resolve().is_relative_to((ROOT / "static").resolve())
                or not path.is_file()
            ):
                return self.send_json({"error": "Not found"}, 404)
            data = path.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type",
                mimetypes.guess_type(str(path))[0] or "application/octet-stream",
            )
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, TypeError) as e:
            self.send_json({"error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    a = p.parse_args()
    print(f"AlphaScope http://127.0.0.1:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
