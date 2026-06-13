#!/usr/bin/env python3
"""Self-contained tests for theme_flow (no network).

A fake `yfinance` module is injected so canned OHLCV series exercise the real
Chaikin-$ money-flow proxy (mfv math, winsorisation, dollar-additive theme
aggregation, 4-bucket capital state, 抄底 divergence, concentration, never-raises)
without the network. load_baskets is monkeypatched to a small controlled taxonomy.

Run:  .venv/bin/python scripts/test_theme_flow.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import theme_flow as tf  # noqa: E402


# ── Fake data helpers ──────────────────────────────────────────────────────────
def _ticker_cols(close, pos=0.0, band=2.0, adj=None, vol=1e6):
    """Build High/Low/Close/Adj Close/Volume Series for one ticker.

    `pos` ∈ [-1,1] is where the close sits in the day's range, so the Chaikin
    multiplier mfm = ((C-L)-(H-C))/(H-L) == pos exactly (verified in the math test):
        H = C - pos*band/2 + band/2 ,  L = C - pos*band/2 - band/2 .
    `adj` (Adj Close) defaults to close; pass a declining series to make a
    price-down / flow-in 抄底 divergence."""
    high = close - pos * band / 2 + band / 2
    low = close - pos * band / 2 - band / 2
    adj = close if adj is None else adj
    volume = pd.Series(float(vol), index=close.index)
    return {"High": high, "Low": low, "Close": close, "Adj Close": adj, "Volume": volume}


def _frame(spec: dict, n=60):
    """MultiIndex (field, ticker) frame like yf.download(auto_adjust=False) output."""
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    per_field: dict[str, dict] = {f: {} for f in
                                  ("High", "Low", "Close", "Adj Close", "Volume")}
    for t, cols in spec.items():
        for fld, series in cols.items():
            per_field[fld][t] = series.reindex(idx) if hasattr(series, "reindex") else series
    frames = []
    for fld, d in per_field.items():
        df = pd.DataFrame(d, index=idx)
        df.columns = pd.MultiIndex.from_product([[fld], df.columns])
        frames.append(df)
    return pd.concat(frames, axis=1)


def _install_fake_yf(download_result=None, raises=False):
    fake = types.ModuleType("yfinance")

    def _download(*a, **k):
        if raises:
            raise RuntimeError("network down")
        return download_result

    fake.download = _download
    sys.modules["yfinance"] = fake


def _rising(n, r, start=100.0):
    return pd.Series(start * np.cumprod(np.full(n, 1 + r)),
                     index=pd.date_range("2024-01-01", periods=n, freq="B"))


def _flat(n, v=100.0):
    return pd.Series(float(v), index=pd.date_range("2024-01-01", periods=n, freq="B"))


# ── Tests ────────────────────────────────────────────────────────────────────
def test_money_flow_volume_math():
    hi = pd.Series([10.0, 11.0]); lo = pd.Series([9.0, 9.0])
    cl = pd.Series([10.0, 9.0]); vol = pd.Series([100.0, 100.0])
    mfv = tf._money_flow_volume(hi, lo, cl, vol)
    # bar0: close==high → mfm=+1 → 1*10*100=1000 ; bar1: close==low → mfm=-1 → -900
    assert abs(float(mfv.iloc[0]) - 1000.0) < 1e-6, mfv.iloc[0]
    assert abs(float(mfv.iloc[1]) + 900.0) < 1e-6, mfv.iloc[1]
    # flat bar (high==low) → multiplier 0, never NaN/inf
    flat = tf._money_flow_volume(pd.Series([5.0]), pd.Series([5.0]),
                                 pd.Series([5.0]), pd.Series([100.0]))
    assert float(flat.iloc[0]) == 0.0


def test_capital_state_buckets():
    eps = 0.02
    assert tf._capital_state(0.5, 0.1, eps) == tf.STATE_INFLOW_ACC
    assert tf._capital_state(0.5, -0.1, eps) == tf.STATE_INFLOW_SLOW
    assert tf._capital_state(0.005, 0.1, eps) == tf.STATE_NEUTRAL    # inside deadband
    assert tf._capital_state(-0.5, 0.1, eps) == tf.STATE_OUTFLOW
    assert tf._capital_state(float("nan"), 0.1, eps) == tf.STATE_NEUTRAL  # NaN guard
    assert set(tf.STATES) == {tf.STATE_INFLOW_ACC, tf.STATE_INFLOW_SLOW,
                              tf.STATE_NEUTRAL, tf.STATE_OUTFLOW}


def test_load_baskets_real_file():
    """The shipped content/theme_baskets.json loads as structured records, and every
    curated parent_sector_etfs value is a valid SPDR key (invalids are dropped)."""
    b = tf.load_baskets()
    assert len(b) >= 25, len(b)
    for name, rec in b.items():
        assert set(rec) == {"desc", "tickers", "reps_hint", "parent_sector_etfs"}
        assert rec["tickers"]
        assert all(p in tf.SPDR_SECTORS for p in rec["parent_sector_etfs"])


def test_winsorisation_caps_a_spike():
    """A single 100× volume bar is clipped to ±K_WINSOR·ADV20, so it can't dominate."""
    n = 40
    close = _flat(n, 100.0)
    cols = _ticker_cols(close, pos=1.0, band=2.0, vol=1_000_000.0)
    cols["Volume"].iloc[-1] = 100_000_000.0          # giant spike on the last bar
    ff = {f: pd.DataFrame({"X": cols[f]}) for f in cols}
    info = tf._per_ticker(ff, "X")
    assert info is not None
    assert info["mfv"].abs().max() <= tf.K_WINSOR * info["adv20"] + 1e-3


def test_illiquid_excluded():
    """A name under the $5M ADV floor is dropped (None), never silently zeroed."""
    close = _flat(40, 1.0)
    cols = _ticker_cols(close, pos=1.0, vol=1000.0)   # ~$1k/day << $5M floor
    ff = {f: pd.DataFrame({"X": cols[f]}) for f in cols}
    assert tf._per_ticker(ff, "X") is None


def test_compute_shape_states_and_bottom_fishing(monkeypatch):
    n = 60
    spec = {
        # inflow & accelerating: close near highs, rising
        "I1": _ticker_cols(_rising(n, 0.004), pos=0.9, vol=2_000_000),
        "I2": _ticker_cols(_rising(n, 0.003), pos=0.8, vol=1_500_000),
        "I3": _ticker_cols(_rising(n, 0.003), pos=0.8, vol=1_200_000),
        # outflow: close near lows
        "O1": _ticker_cols(_flat(n, 50.0), pos=-0.9, vol=2_000_000),
        "O2": _ticker_cols(_flat(n, 50.0), pos=-0.8, vol=1_500_000),
        "O3": _ticker_cols(_flat(n, 50.0), pos=-0.8, vol=1_200_000),
        # 抄底: intraday buying (pos>0 → mfv>0) but Adj Close declining → ret_5d<0
        "B1": _ticker_cols(_flat(n, 80.0), pos=0.9, adj=_rising(n, -0.01, 80.0), vol=2_000_000),
        "B2": _ticker_cols(_flat(n, 80.0), pos=0.8, adj=_rising(n, -0.01, 80.0), vol=1_500_000),
        "B3": _ticker_cols(_flat(n, 80.0), pos=0.8, adj=_rising(n, -0.01, 80.0), vol=1_200_000),
        "SPY": _ticker_cols(_rising(n, 0.0005), pos=0.5, vol=5_000_000),
    }
    _install_fake_yf(_frame(spec, n))
    monkeypatch_baskets({
        "資金流入主題": {"desc": "", "tickers": ["I1", "I2", "I3"],
                     "reps_hint": [], "parent_sector_etfs": ["XLK"]},
        "資金流出主題": {"desc": "", "tickers": ["O1", "O2", "O3"],
                     "reps_hint": [], "parent_sector_etfs": ["XLF"]},
        "抄底主題": {"desc": "", "tickers": ["B1", "B2", "B3"],
                  "reps_hint": [], "parent_sector_etfs": ["XLV"]},
    })
    out = tf._compute_theme_flow()
    assert out is not None and len(out["themes"]) == 3
    by = {r["theme"]: r for r in out["themes"]}

    assert by["資金流入主題"]["flow_5d_norm"] > 0
    assert by["資金流入主題"]["capital_state"] in (tf.STATE_INFLOW_ACC, tf.STATE_INFLOW_SLOW)
    assert by["資金流出主題"]["flow_5d_norm"] < 0
    assert by["資金流出主題"]["capital_state"] == tf.STATE_OUTFLOW
    # 抄底: price down, proxy-flow in
    assert by["抄底主題"]["ret_5d"] < 0 and by["抄底主題"]["flow_5d_norm"] > 0
    assert by["抄底主題"]["bottom_fishing"] is True
    assert "抄底主題" in out["bottom_fishing"]

    for r in out["themes"]:
        assert 0.0 <= (r["heat_score"] or 0) <= 100.0
        assert r["capital_state"] in tf.STATES
        assert r["n_used"] == 3 and r["n_total"] == 3
        assert 0.0 <= (r["top_share"] or 0) <= 1.0
        assert len(r["reps"]) >= 1
    assert set(out["buckets"]) == set(tf.STATES)


def test_concentration_flag(monkeypatch):
    n = 60
    # I1 dwarfs the others in dollar flow → top_share high → high_concentration True
    spec = {
        "D1": _ticker_cols(_rising(n, 0.003), pos=0.9, vol=50_000_000),
        "D2": _ticker_cols(_rising(n, 0.003), pos=0.9, vol=600_000),
        "D3": _ticker_cols(_rising(n, 0.003), pos=0.9, vol=600_000),
        "SPY": _ticker_cols(_rising(n, 0.0005), pos=0.5, vol=5_000_000),
    }
    _install_fake_yf(_frame(spec, n))
    monkeypatch_baskets({"龍頭主導": {"desc": "", "tickers": ["D1", "D2", "D3"],
                                  "reps_hint": [], "parent_sector_etfs": ["XLK"]}})
    out = tf._compute_theme_flow()
    assert out is not None
    r = out["themes"][0]
    assert r["top_share"] >= 0.6 and r["high_concentration"] is True
    assert r["reps"][0]["ticker"] == "D1"     # ranked first by 20d cumulative flow


def test_never_raises_on_download_error(monkeypatch):
    _install_fake_yf(raises=True)
    monkeypatch_baskets({"X": {"desc": "", "tickers": ["A", "B", "C"],
                              "reps_hint": [], "parent_sector_etfs": ["XLK"]}})
    assert tf._compute_theme_flow() is None       # never raises → None


def test_empty_returns_none(monkeypatch):
    _install_fake_yf(pd.DataFrame())
    monkeypatch_baskets({"X": {"desc": "", "tickers": ["A", "B", "C"],
                              "reps_hint": [], "parent_sector_etfs": ["XLK"]}})
    assert tf._compute_theme_flow() is None


def test_no_baskets_returns_none(monkeypatch):
    _install_fake_yf(pd.DataFrame())
    monkeypatch_baskets({})
    assert tf._compute_theme_flow() is None


def test_theme_insider_aggregation(monkeypatch):
    """gather_theme_insider sums REAL Form-4 net shares × price into a $ net-buy per
    theme (full coverage here, so it passes the thin-coverage floor)."""
    n = 5
    spec = {"AAA": _ticker_cols(_flat(n, 100.0)),
            "BBB": _ticker_cols(_flat(n, 50.0)),
            "CCC": _ticker_cols(_flat(n, 10.0))}
    _install_fake_yf(_frame(spec, n))
    fake_inst = types.ModuleType("institutional_free")
    NET = {"AAA": 1000.0, "BBB": -500.0, "CCC": 0.0}    # CCC: covered, flat

    def _gi(t):
        ns = NET.get(t)
        return {"insider_6m": {"net_shares": ns}} if ns is not None else {}

    fake_inst.gather_institutional = _gi
    sys.modules["institutional_free"] = fake_inst
    monkeypatch_baskets({"主題X": {"desc": "", "tickers": ["AAA", "BBB", "CCC"],
                                 "reps_hint": [], "parent_sector_etfs": ["XLK"]}})
    out = tf._compute_theme_insider()
    sys.modules.pop("institutional_free", None)
    assert out is not None
    bt = out["by_theme"]["主題X"]
    # 1000×100 + (-500)×50 + 0×10 = 75000 ; coverage 3/3 passes the floor
    assert bt["insider_net_usd"] == 75000.0, bt
    assert bt["n_buy"] == 1 and bt["n_sell"] == 1, bt
    assert bt["n_cov"] == 3 and bt["n_total"] == 3, bt


def test_insider_thin_coverage_suppressed(monkeypatch):
    """One covered name must NOT speak for a basket: a theme below the coverage
    floor (n_cov < MIN_USED or < 50%) emits NO insider value → no divergence flag
    can fire from a single ticker (Codex TF-1 M1 regression)."""
    n = 5
    spec = {"AAA": _ticker_cols(_flat(n, 100.0)),
            "BBB": _ticker_cols(_flat(n, 50.0)),
            "CCC": _ticker_cols(_flat(n, 10.0))}
    _install_fake_yf(_frame(spec, n))
    fake_inst = types.ModuleType("institutional_free")

    def _gi(t):  # only AAA has insider data → n_cov=1 of 3
        return {"insider_6m": {"net_shares": 1000.0}} if t == "AAA" else {}

    fake_inst.gather_institutional = _gi
    sys.modules["institutional_free"] = fake_inst
    monkeypatch_baskets({"薄主題": {"desc": "", "tickers": ["AAA", "BBB", "CCC"],
                                 "reps_hint": [], "parent_sector_etfs": ["XLK"]}})
    out = tf._compute_theme_insider()
    sys.modules.pop("institutional_free", None)
    assert out is None, out  # the only theme is suppressed → whole overlay None


def test_chunk_failure_suppresses_theme(monkeypatch):
    """Download failures count AGAINST coverage (full curated denominator): a theme
    where a chunk outage leaves 3/7 names must be SUPPRESSED, not shipped as a
    confident cov=1.0 board (Codex TF-1 H1 regression). A healthy 3/5 ships."""
    n = 60
    spec = {
        "A1": _ticker_cols(_rising(n, 0.003), pos=0.8, vol=2_000_000),
        "A2": _ticker_cols(_rising(n, 0.003), pos=0.8, vol=1_500_000),
        "A3": _ticker_cols(_rising(n, 0.003), pos=0.8, vol=1_200_000),
        "SPY": _ticker_cols(_rising(n, 0.0005), pos=0.5, vol=5_000_000),
    }  # F1..F4 / G1..G2 get NO data → land in `failed`
    _install_fake_yf(_frame(spec, n))
    monkeypatch_baskets({
        "壞主題": {"desc": "", "tickers": ["A1", "A2", "A3", "F1", "F2", "F3", "F4"],
                "reps_hint": [], "parent_sector_etfs": ["XLK"]},   # 3/7 = 0.43 < 0.5
        "好主題": {"desc": "", "tickers": ["A1", "A2", "A3", "G1", "G2"],
                "reps_hint": [], "parent_sector_etfs": ["XLK"]},   # 3/5 = 0.60 ≥ 0.5
    })
    out = tf._compute_theme_flow()
    assert out is not None
    names = [r["theme"] for r in out["themes"]]
    assert names == ["好主題"], names           # 壞主題 suppressed, NOT ranked
    good = out["themes"][0]
    assert good["n_used"] == 3 and good["n_total"] == 5 and good["n_failed"] == 2
    assert out["n_failed_download"] >= 6        # F1-F4 + G1-G2 all counted


def test_llm_insider_divergence_whitelist():
    """An LLM insider divergence survives ONLY when the verified numbers truly
    diverge: covered insider data AND sign disagreement with the proxy flow.
    Hallucinated themes, suppressed (thin-coverage) themes, AND covered themes
    whose insider direction AGREES with the flow must all be DROPPED before
    persisting — model output can't be laundered as real-money evidence
    (Codex TF-1 M2 + r3 sign-validation regression)."""
    import theme_rotation as tr
    verified = {"themes": [
        # insiders SELL (−) while proxy flows IN (+) → true divergence
        {"theme": "真背離主題", "insider_net_usd_6m": -5e6, "flow_5d_norm": 1.2},
        # insiders BUY (+) while proxy flows OUT (−) → true divergence
        {"theme": "逆勢買主題", "insider_net_usd_6m": 3e6, "flow_5d_norm": -0.8},
        # covered but ALIGNED (both negative) → NOT a divergence
        {"theme": "同向主題", "insider_net_usd_6m": -2e6, "flow_5d_norm": -0.9},
        # covered but flow exactly 0 → no direction to diverge from
        {"theme": "零流向主題", "insider_net_usd_6m": 4e6, "flow_5d_norm": 0.0},
        # covered, opposing SIGN but inside the board's neutral deadband
        # (|flow| ≤ EPS_X=0.30 → 中性 on the board, no direction) → NOT a divergence
        {"theme": "死區負流主題", "insider_net_usd_6m": 4e6, "flow_5d_norm": -0.1},
        {"theme": "死區正流主題", "insider_net_usd_6m": -4e6, "flow_5d_norm": 0.29},
        {"theme": "被壓制主題"},                       # thin coverage → no insider key
    ]}
    read = {"headline": "x", "insider_divergence": [
        {"theme": "真背離主題", "name": "ok", "why": "real divergence"},
        {"theme": "逆勢買主題", "name": "ok", "why": "real divergence"},
        {"theme": "同向主題", "name": "bad", "why": "aligned, not a divergence"},
        {"theme": "零流向主題", "name": "bad", "why": "no flow direction"},
        {"theme": "死區負流主題", "name": "bad", "why": "neutral-deadband flow"},
        {"theme": "死區正流主題", "name": "bad", "why": "neutral-deadband flow"},
        {"theme": "被壓制主題", "name": "bad", "why": "no covered data"},
        {"theme": "幻覺主題", "name": "bad", "why": "hallucinated"},
        "not-a-dict",
    ]}
    out = tr._filter_insider_divergence(read, verified)
    kept = [h["theme"] for h in out["insider_divergence"]]
    assert kept == ["真背離主題", "逆勢買主題"], kept


def test_llm_insider_prose_bypass_rejected():
    """Insider evidence is CHANNEL-SEPARATED: insider/Form-4/內部人 wording in
    ANY channel other than a whitelisted structured insider_divergence entry
    rejects the WHOLE read — earlier theme-name blacklisting was alias-able
    (shortened names slipped every substring check), so no name matching is
    involved at all (Codex TF-1 r5/r6/r8 regressions)."""
    import theme_rotation as tr
    verified = {"themes": [
        {"theme": "真背離主題", "insider_net_usd_6m": -5e6, "flow_5d_norm": 1.2},
        {"theme": "同向主題", "insider_net_usd_6m": -2e6, "flow_5d_norm": -0.9},
    ]}

    def _rejected(read):
        try:
            tr._filter_insider_divergence(read, verified)
            return False
        except ValueError:
            return True

    # Insider wording per non-whitelisted channel → all reject (r5).
    assert _rejected({"headline": "同向主題 內部人大買,跟進", "insider_divergence": []})
    assert _rejected({"headline": "x", "next_thesis": "同向主題有 Form-4 buying 支撐",
                      "insider_divergence": []})
    assert _rejected({"headline": "x", "caveats": ["同向主題 insider 賣壓是隱憂"],
                      "insider_divergence": []})
    assert _rejected({"headline": "x", "accelerating_in": [
        {"theme": "同向主題", "name": "n", "why": "內部人也同步買超"}],
        "insider_divergence": []})
    # Decorated theme LABEL smuggling the claim, name/why clean (r6).
    assert _rejected({"headline": "x", "rotating_out": [
        {"theme": "同向主題 內部人大買", "name": "n", "why": "clean"}],
        "insider_divergence": []})
    # ALIASED/shortened theme name + insider wording: no substring of a known
    # theme matches, but the marker alone rejects (r8 — alias-proof).
    assert _rejected({"headline": "x", "accelerating_in": [
        {"theme": "同向", "name": "n", "why": "內部人也同步買超"}],
        "insider_divergence": []})
    # Even an LLM-written generic insider caveat rejects — the standard caveat
    # is appended by CODE after validation, never written by the model.
    assert _rejected({"headline": "x", "caveats": ["內部人資料為 6 個月聚合"],
                      "insider_divergence": []})
    # Headline mentioning insiders rejects even for a whitelisted theme — the
    # structured entry is the only channel.
    assert _rejected({"headline": "真背離主題 內部人逆勢買", "insider_divergence": []})
    # The happy path: insider wording confined to whitelisted structured
    # entries; everything else insider-free → accepted, non-whitelisted entries
    # silently dropped, and the kept entry's text is REBUILT by code.
    ok = {"headline": "資金輪動中", "caveats": ["proxy 非真實買賣超"],
          "insider_divergence": [
              {"theme": "真背離主題", "name": "n", "why": "Form-4 內部人逆勢買"},
              {"theme": "同向主題", "name": "n", "why": "aligned — must drop"}]}
    out = tr._filter_insider_divergence(ok, verified)
    assert [h["theme"] for h in out["insider_divergence"]] == ["真背離主題"]


def test_llm_insider_divergence_text_is_code_owned():
    """A kept (whitelisted) insider_divergence entry must render CODE-OWNED text
    derived from the verified numbers — the LLM's name/why never render, so it
    cannot state the wrong buy/sell side (Codex TF-1 r9 regression: whitelist
    proved a divergence existed but didn't bind the text to the real direction)."""
    import theme_rotation as tr
    verified = {"themes": [
        # insiders net-SOLD $5M while proxy flowed IN → the only honest copy is 賣超
        {"theme": "真背離主題", "desc": "描述A", "insider_net_usd_6m": -5e6,
         "flow_5d_norm": 1.2},
        # insiders net-BOUGHT $3M while proxy flowed OUT → honest copy is 買超
        {"theme": "逆勢買主題", "desc": "描述B", "insider_net_usd_6m": 3e6,
         "flow_5d_norm": -0.8},
    ]}
    read = {"headline": "x", "insider_divergence": [
        # LLM claims the OPPOSITE side in both why texts (and a junk name) —
        # plus a duplicate that must dedupe.
        {"theme": "真背離主題", "name": "junk", "why": "Form-4 內部人逆勢買進"},
        {"theme": "真背離主題", "name": "dup", "why": "內部人買"},
        {"theme": "逆勢買主題", "name": "junk", "why": "內部人大舉賣出"},
    ]}
    out = tr._filter_insider_divergence(read, verified)
    ents = {h["theme"]: h for h in out["insider_divergence"]}
    assert set(ents) == {"真背離主題", "逆勢買主題"} and len(out["insider_divergence"]) == 2
    sell = ents["真背離主題"]
    assert "賣超" in sell["why"] and "$5.0M" in sell["why"] and "流入" in sell["why"], sell
    assert "逆勢買" not in sell["why"] and sell["name"] == "描述A", sell
    buy = ents["逆勢買主題"]
    assert "買超" in buy["why"] and "$3.0M" in buy["why"] and "流出" in buy["why"], buy
    assert "賣出" not in buy["why"] and buy["name"] == "描述B", buy


def test_stale_read_rejected_at_render():
    """A persisted report from BEFORE a validation tightening (missing/older
    validation_version) must not render — is_current_read is the render
    boundary (Codex TF-1 r5 regression)."""
    import theme_rotation as tr
    assert not tr.is_current_read(None)
    assert not tr.is_current_read({"status": "ready"})                      # pre-fix report
    assert not tr.is_current_read({"status": "ready", "validation_version": 1})
    # v2 = r5 validator (missed decorated item labels); v3 = r6 (alias-able
    # name blacklist); v4 = r8 (channel separation but LLM-authored entry text
    # could state the wrong side). Reports from ALL must be invalidated.
    for old in (2, 3, 4, 5, 6):
        assert not tr.is_current_read({"status": "ready", "validation_version": old})
    assert not tr.is_current_read({"status": "error",
                                   "validation_version": tr.VALIDATION_VERSION})
    assert tr.VALIDATION_VERSION >= 7


def test_read_bound_to_board_fingerprint():
    """A ready, current-version report must ALSO bind to the exact board it was
    generated from: the renderer recomputes the fingerprint from the live flow
    and refuses a read whose board differs — stale Form-4 divergence claims
    must not render as current evidence (Codex TF-1 r11 regression)."""
    import theme_rotation as tr
    themes = [{"theme": "A", "flow_5d_norm": 1.234567},
              {"theme": "B", "flow_5d_norm": -0.5}]
    fp = tr.board_fingerprint("2026-06-13", themes)
    ok = {"status": "ready", "validation_version": tr.VALIDATION_VERSION,
          "board_fingerprint": fp}
    assert tr.is_current_read(ok, board_fp=fp)
    # Same board expressed via the (richer) verified rows → same fingerprint.
    verified_rows = [{**t, "state": "中性", "insider_net_usd_6m": 1e6} for t in themes]
    assert tr.board_fingerprint("2026-06-13", verified_rows) == fp
    # Different as_of, a changed flow value, or a missing/legacy fingerprint → stale.
    assert tr.board_fingerprint("2026-06-12", themes) != fp
    moved = [{"theme": "A", "flow_5d_norm": 1.3}, themes[1]]
    assert not tr.is_current_read(ok, board_fp=tr.board_fingerprint("2026-06-13", moved))
    legacy = {"status": "ready", "validation_version": tr.VALIDATION_VERSION}
    assert not tr.is_current_read(legacy, board_fp=fp)
    # Without a fingerprint argument only the version/status gate applies.
    assert tr.is_current_read(legacy)


def test_confidence_is_closed_enum():
    """confidence renders directly in the UI chip, so free text there could
    smuggle insider wording past the channel guard — only high|medium|low
    survive normalization; anything else becomes '—' (Codex TF-1 r10)."""
    import theme_rotation as tr
    base = {"headline": "x"}
    smug = tr._normalize_read({**base, "confidence": "high - 同向主題 內部人大買"})
    assert smug["confidence"] == "—", smug["confidence"]
    assert tr._normalize_read({**base, "confidence": "form-4 buy"})["confidence"] == "—"
    assert tr._normalize_read({**base, "confidence": None})["confidence"] == "—"
    assert tr._normalize_read({**base, "confidence": 0.9})["confidence"] == "—"
    for ok in ("high", "medium", "low", " High "):
        assert tr._normalize_read({**base, "confidence": ok})["confidence"] == ok.strip().lower()
    assert tr.is_current_read({"status": "ready",
                               "validation_version": tr.VALIDATION_VERSION})


# ── Minimal monkeypatch shim (no pytest dependency, mirrors test_sector_flow) ───
_ORIG_LOAD = tf.load_baskets


def monkeypatch_baskets(d):
    tf.load_baskets = lambda: d


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            t(None) if t.__code__.co_argcount else t()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
        finally:
            tf.load_baskets = _ORIG_LOAD       # restore between tests
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
