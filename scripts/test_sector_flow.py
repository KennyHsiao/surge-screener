#!/usr/bin/env python3
"""Self-contained tests for sector_flow.gather_sector_flow (no network).

A fake `yfinance` module is injected so canned ETF+SPY price series exercise the
real RRG math (RS-Ratio / RS-Momentum / quadrant / heat / tail) without the
network. Covers: quadrant classification (pure fn), full-shape extraction +
direction (rising-ratio ETF reads RS-Ratio>100, falling reads <100), heat bounds,
never-raises on download error, and empty/insufficient → None.

Run:  .venv/bin/python scripts/test_sector_flow.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import sector_flow as sf  # noqa: E402


def _make_data(n=520):
    """MultiIndex (field, ticker) frame like yf.download multi-ticker output.

    SPY steady up; XLK durably outperforms (ratio持續 above its baseline → RS-Ratio>100);
    XLP durably underperforms (ratio持續 below baseline → RS-Ratio<100). Monotone so the
    long-baseline normalisation reads them unambiguously."""
    idx = pd.date_range("2023-01-01", periods=n, freq="B")
    spy = pd.Series(100 * np.cumprod(1 + np.full(n, 0.0004)), index=idx)
    up = pd.Series(100 * np.cumprod(1 + np.full(n, 0.0009)), index=idx)   # outperforms SPY
    dn = pd.Series(100 * np.cumprod(1 + np.full(n, 0.0001)), index=idx)   # lags SPY
    close = pd.DataFrame({"SPY": spy, "XLK": up, "XLP": dn})
    vol = pd.DataFrame({c: pd.Series(1_000_000.0, index=idx) for c in close.columns})
    return pd.concat({"Close": close, "Volume": vol}, axis=1)


def _install_fake_yf(download_result=None, raises=False):
    fake = types.ModuleType("yfinance")

    def _download(*a, **k):
        if raises:
            raise RuntimeError("network down")
        return download_result

    fake.download = _download
    sys.modules["yfinance"] = fake


# ── Tests ────────────────────────────────────────────────────────────────────
def test_quadrant_pure_fn():
    assert sf._quadrant(101, 101) == "Leading"
    assert sf._quadrant(101, 99) == "Weakening"
    assert sf._quadrant(99, 99) == "Lagging"
    assert sf._quadrant(99, 101) == "Improving"
    assert sf._quadrant(100, 100) == "Leading"   # boundary inclusive
    assert set(sf.QUADRANT_ZH) == {"Leading", "Weakening", "Lagging", "Improving"}


def test_full_shape_and_direction():
    _install_fake_yf(_make_data())
    out = sf._compute_sector_flow()
    assert out is not None
    assert out["benchmark"] == "SPY"
    etfs = {r["etf"] for r in out["sectors"]}
    assert etfs == {"XLK", "XLP"}, etfs  # only those with provided data
    by = {r["etf"]: r for r in out["sectors"]}

    for r in out["sectors"]:
        assert isinstance(r["rs_ratio"], float) and isinstance(r["rs_momentum"], float)
        assert r["quadrant"] in sf.QUADRANT_ZH
        assert 0.0 <= r["heat_score"] <= 100.0
        assert isinstance(r["tail"], list) and r["tail"]
        assert {"date", "rs_ratio", "rs_momentum"} <= set(r["tail"][0])
        # metadata carried through from SECTOR_ETFS
        assert r["name_zh"] and r["group"] in ("主板塊", "主題")

    # Direction: accelerating outperformer above 100, fading underperformer below.
    assert by["XLK"]["rs_ratio"] > 100, by["XLK"]["rs_ratio"]
    assert by["XLP"]["rs_ratio"] < 100, by["XLP"]["rs_ratio"]

    # leaders/improving are consistent with the per-row quadrants.
    for etf in out["leaders"]:
        assert by[etf]["quadrant"] == "Leading"
    for etf in out["improving"]:
        assert by[etf]["quadrant"] == "Improving"


def test_theme_tag_present():
    """A thematic ETF in the config carries its theme label (e.g. AI 超級循環)."""
    smh = next(s for s in sf.SECTOR_ETFS if s["etf"] == "SMH")
    assert smh["group"] == "主題" and smh["theme"] == "AI 超級循環"


def test_never_raises_on_download_error():
    _install_fake_yf(raises=True)
    assert sf._compute_sector_flow() is None


def test_empty_returns_none():
    _install_fake_yf(pd.DataFrame())
    assert sf._compute_sector_flow() is None


def test_insufficient_history_returns_none():
    _install_fake_yf(_make_data(n=40))  # < RS_WINDOW+MOM_WINDOW+10
    assert sf._compute_sector_flow() is None


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
