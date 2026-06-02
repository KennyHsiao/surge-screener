#!/usr/bin/env python3
"""Self-contained tests for analyst_free.gather_analyst_views (no network).

A fake `yfinance` module is injected into sys.modules so the canned yfinance
shapes (DataFrames + the price-targets DICT) exercise the real transform logic
without hitting the network. Covers: full-shape extraction, the upside-vs-spot
math + its div-by-zero guard, recent-action date sorting, the never-raises
guarantee, and the all-empty -> None path.

Run:  .venv/bin/python scripts/test_analyst_free.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd  # noqa: E402

import analyst_free as af  # noqa: E402


# ── Canned yfinance shapes (match the real attributes observed on yf 1.3.0) ──
def _rec_summary():
    return pd.DataFrame(
        [{"period": "0m", "strongBuy": 10, "buy": 48, "hold": 2, "sell": 1, "strongSell": 0},
         {"period": "-1m", "strongBuy": 9, "buy": 47, "hold": 3, "sell": 1, "strongSell": 0}])


def _upgrades():
    # Index = GradeDate Timestamps, intentionally NOT pre-sorted (older first).
    idx = pd.to_datetime(["2026-05-21 16:00:00", "2026-06-01 17:00:00"])
    return pd.DataFrame({
        "Firm": ["UBS", "DA Davidson"],
        "ToGrade": ["Buy", "Buy"],
        "FromGrade": ["Neutral", "Buy"],
        "Action": ["up", "main"],
        "priceTargetAction": ["Raises", "Maintains"],
        "currentPriceTarget": [280.0, 300.0],
        "priorPriceTarget": [275.0, 300.0],
    }, index=idx)


def _earnings_estimate():
    return pd.DataFrame(
        {"avg": [2.07925, 8.9427], "numberOfAnalysts": [40, 47], "growth": [0.98, 0.875]},
        index=pd.Index(["0q", "0y"], name="period"))


def _eps_revisions():
    return pd.DataFrame(
        {"upLast30days": [34, 41], "downLast30days": [3, 2]},
        index=pd.Index(["0q", "0y"], name="period"))


class _DummyTk:
    """Mimics yf.Ticker. raises=True makes EVERY analyst attribute raise."""

    def __init__(self, *, info=None, rs=None, ud=None, apt=None, ee=None, er=None,
                 raises=False):
        self._info = info or {}
        self._rs, self._ud, self._apt = rs, ud, apt
        self._ee, self._er = ee, er
        self._raises = raises

    def _g(self, v):
        if self._raises:
            raise RuntimeError("source unavailable")
        return v

    @property
    def info(self):
        return self._g(self._info)

    @property
    def recommendations_summary(self):
        return self._g(self._rs)

    @property
    def upgrades_downgrades(self):
        return self._g(self._ud)

    @property
    def analyst_price_targets(self):
        return self._g(self._apt)

    @property
    def earnings_estimate(self):
        return self._g(self._ee)

    @property
    def eps_revisions(self):
        return self._g(self._er)


def _install_fake_yf(dummy):
    fake = types.ModuleType("yfinance")
    fake.Ticker = lambda _t: dummy
    sys.modules["yfinance"] = fake


def _full_dummy(**overrides):
    kw = dict(
        info={"recommendationKey": "strong_buy", "numberOfAnalystOpinions": 58,
              "recommendationMean": 1.29508},
        rs=_rec_summary(),
        ud=_upgrades(),
        apt={"current": 224.36, "high": 500.0, "low": 180.0, "mean": 296.81, "median": 285.0},
        ee=_earnings_estimate(), er=_eps_revisions(),
    )
    kw.update(overrides)
    return _DummyTk(**kw)


# ── Tests ────────────────────────────────────────────────────────────────────
def test_num_pct_coercion():
    assert af._num(None) is None
    assert af._num("x") is None
    assert af._num(float("nan")) is None
    assert af._num("3.5") == 3.5
    assert af._pct(0.875) == 87.5
    assert af._pct(None) is None


def test_full_shape_and_upside():
    _install_fake_yf(_full_dummy())
    out = af._compute_analyst_views("NVDA")
    assert out is not None
    assert out["ticker"] == "NVDA" and out["source"] == "yfinance_free"
    # consensus
    assert out["consensus"]["recommendation"] == "strong_buy"
    assert out["consensus"]["num_analysts"] == 58.0
    # distribution = most-recent row (0m), not -1m
    assert out["rating_distribution"]["buy"] == 48.0
    assert out["rating_distribution"]["strong_sell"] == 0.0
    # price targets + upside (296.81-224.36)/224.36*100 ≈ 32.3
    pt = out["price_targets"]
    assert pt["spot"] == 224.36 and pt["mean"] == 296.81
    assert abs(pt["upside_pct"] - 32.3) < 0.2, pt["upside_pct"]
    # estimate revisions (growth fraction -> pct; up/down carried)
    rev = out["estimate_revisions"]["eps_curr_q"]
    assert rev["growth_pct"] == 98.0 and rev["up_last_30d"] == 34.0


def test_recent_actions_sorted_newest_first():
    _install_fake_yf(_full_dummy())
    out = af._compute_analyst_views("NVDA")
    actions = out["recent_actions"]
    assert actions[0]["date"] == "2026-06-01", actions  # newest first despite unsorted input
    assert actions[0]["firm"] == "DA Davidson"
    assert actions[1]["from_grade"] == "Neutral"


def test_upside_divzero_guard():
    """Zero/negative spot must yield upside None, never raise."""
    _install_fake_yf(_full_dummy(
        apt={"current": 0.0, "high": 10.0, "low": 5.0, "mean": 8.0, "median": 7.0}))
    out = af._compute_analyst_views("ZERO")
    assert out["price_targets"]["upside_pct"] is None


def test_never_raises_on_source_error():
    """Every attribute raising -> got_any False -> None, no exception."""
    _install_fake_yf(_DummyTk(raises=True))
    assert af._compute_analyst_views("BAD") is None


def test_all_empty_returns_none():
    """Truthy Ticker but no usable data anywhere -> None."""
    _install_fake_yf(_DummyTk(
        info={}, rs=pd.DataFrame(), ud=pd.DataFrame(),
        apt={}, ee=pd.DataFrame(), er=pd.DataFrame()))
    assert af._compute_analyst_views("EMPTY") is None


def test_partial_data_survives():
    """One good block (consensus) + everything else empty -> still returns it."""
    _install_fake_yf(_DummyTk(
        info={"recommendationKey": "buy", "numberOfAnalystOpinions": 12},
        rs=pd.DataFrame(), ud=pd.DataFrame(), apt={},
        ee=pd.DataFrame(), er=pd.DataFrame()))
    out = af._compute_analyst_views("PART")
    assert out is not None and out["consensus"]["recommendation"] == "buy"
    assert "price_targets" not in out and "rating_distribution" not in out


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
