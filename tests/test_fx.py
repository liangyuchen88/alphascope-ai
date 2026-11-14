import sys, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from email.utils import format_datetime
from fx import parse_ecb, pair_rows, scan_triangles


def quotes(t=1000.0):
    return [
        {
            "pair": p,
            "bid": bid,
            "ask": ask,
            "bid_base_size": 1e6,
            "ask_base_size": 1e6,
            "observed_epoch": t,
            "server_date": format_datetime(
                dt.datetime.fromtimestamp(t, dt.timezone.utc), usegmt=True
            ),
            "url": "https://example.test/UNIT-TEST",
        }
        for p, bid, ask in [
            ("EUR/USD", 1.099, 1.1),
            ("EUR/GBP", 0.9, 0.901),
            ("GBP/USD", 1.299, 1.3),
        ]
    ]


def test_ecb_parser_and_cross_rate_orientation():
    raw = b'<Envelope><Cube><Cube time="2026-11-13"><Cube currency="USD" rate="1.1"/><Cube currency="GBP" rate="0.8"/></Cube></Cube></Envelope>'
    rows = parse_ecb(raw)
    h = {"rows": rows}
    assert pair_rows(h, "EUR/USD")[0]["close"] == 1.1
    assert pair_rows(h, "GBP/USD")[0]["close"] == pytest.approx(1.375)
    eurusd = pair_rows(h, "EUR/USD")[0]["close"]
    usdgbp = pair_rows(h, "USD/GBP")[0]["close"]
    gbpeur = pair_rows(h, "GBP/EUR")[0]["close"]
    assert eurusd * usdgbp * gbpeur == pytest.approx(1)


def test_triangle_uses_ask_to_buy_and_bid_to_sell():
    r = scan_triangles(quotes(), fee_bps=0, slippage_bps=0, as_of=1000.0)
    first = r["routes"][0]
    assert first["final_amount"] == pytest.approx(1000 / 1.1 * 0.9 * 1.299)
    assert first["positive_candidate"]
    assert not first["execution_verified"] and not r["executable_arbitrage_verified"]
    assert first["legs"][0]["side"] == "buy base at ask"


def test_fees_and_slippage_are_charged_on_all_three_legs():
    free = scan_triangles(quotes(), fee_bps=0, slippage_bps=0, as_of=1000.0)["routes"][
        0
    ]
    paid = scan_triangles(quotes(), fee_bps=20, slippage_bps=2, as_of=1000.0)["routes"][
        0
    ]
    assert paid["final_amount"] == pytest.approx(
        free["final_amount"] * (1 - 0.002) ** 3 * (1 - 0.0002) ** 3
    )


def test_stale_or_skewed_quotes_never_qualify_as_candidates():
    q = quotes()
    q[0]["observed_epoch"] = 980
    r = scan_triangles(q, as_of=1000.0)
    assert not r["quote_quality_ok"]
    assert all(not x["positive_candidate"] for x in r["routes"])


def test_capacity_limits_are_checked_each_leg():
    q = quotes()
    q[1]["bid_base_size"] = 1
    r = scan_triangles(q, fee_bps=0, slippage_bps=0, as_of=1000.0)
    assert not r["routes"][0]["positive_candidate"]
    assert not r["routes"][0]["top_level_capacity_ok"]


def test_crossed_books_and_invalid_costs_are_rejected():
    q = quotes()
    q[0]["bid"] = 2
    with pytest.raises(ValueError):
        scan_triangles(q, as_of=1000.0)
    with pytest.raises(ValueError):
        scan_triangles(quotes(), fee_bps=-1, as_of=1000.0)
    with pytest.raises(ValueError):
        scan_triangles(quotes(), start="JPY", as_of=1000.0)
