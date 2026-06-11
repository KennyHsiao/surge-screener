#!/usr/bin/env python3
"""Live factor check-up — apply the retro-VALIDATED surge factors to a stock TODAY.

The retrospective pipeline measured which pre-surge factors actually have lift.
This reuses the SAME reconstruction (retro_reconstruct.reconstruct_flags) but with
t0 = the latest session, so "what setup did a pre-surge stock show at lift-off"
becomes "what does THIS stock show right now". The live flags are then scored
against the validated lift table (reports/retrospective/factor_lift.json) into a
directional 暴漲傾向 band, plus the trader archetypes (config/retro_modules.json)
it matches.

CRITICAL — fail-closed inheritance: the retro model is survivorship-biased and
small-sample, so retro_factor_lift always sets recommendations_blocked=True. This
module inherits that gate (`blocked`): the band is DIRECTIONAL ONLY, never a
trading-signal threshold. We weight matched factors by lift (NOT a probability
product — the factors are correlated, so an independence assumption is invalid);
the band is "validated-factor coverage", not a calibrated probability.

CLI:
    python scripts/live_factors.py NVDA
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
LIFT_PATH = REPO / "reports" / "retrospective" / "factor_lift.json"
EVENTS_PATH = REPO / "reports" / "retrospective" / "surge_events.json"
FEATURES_PATH = REPO / "reports" / "retrospective" / "surge_features.json"
MODULES_PATH = REPO / "config" / "retro_modules.json"

import momentum_options as mo  # noqa: E402 — live indicator engine (also used by retro)
import retro_reconstruct as rr  # noqa: E402 — reconstruct_flags works for any t0
import retro_factor_lift as rfl  # noqa: E402 — canonical fail-closed gate
import retro_modules as rm  # noqa: E402 — trader-archetype matching
import cache  # noqa: E402 — best-effort TTL disk cache

_SUPPORT_K = 10.0          # support shrinkage: weight ∝ support/(support+K)
_LIFT_CAP = 4.0            # cap |lift-1| so one factor can't dominate the band
_BAND_LABELS = ["很低", "低", "中", "中偏高", "高"]
_CAVEAT = ("暴漲傾向為方向性參考,非交易訊號:復盤模型因樣本不足/倖存者偏誤,建議一律"
           "封鎖,須跑滿全宇宙 + point-in-time 成分資料才可能解鎖。")


def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    """tz-naive, normalized DatetimeIndex so `df.index <= t0` aligns with a date t0."""
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def fetch_spy_vix(period: str = "1y") -> tuple[pd.Series, pd.Series]:
    """SPY / ^VIX close as of now — same fetch retro_factor_lift uses for Dim5.
    Fetch ONCE per batch and pass into live_factor_flags() to avoid N refetches."""
    import yfinance as yf
    spy = yf.Ticker("SPY").history(period=period, auto_adjust=False)["Close"].dropna()
    vix = yf.Ticker("^VIX").history(period=period)["Close"].dropna()
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
    return spy, vix


def live_factor_flags(ticker: str, as_of=None, spy_close=None, vix_close=None,
                      use_cache: bool = True) -> dict | None:
    """The 15 Dim1/Dim5 boolean factor flags (True/False/None) for `ticker` as of
    today (or `as_of`). None = insufficient data — never treat as False.

    Pass spy_close/vix_close to reuse one market fetch across a batch."""
    ticker = ticker.upper().strip().lstrip("$")
    stamp = (pd.Timestamp(as_of) if as_of
             else pd.Timestamp.now(tz="UTC").tz_localize(None)).normalize()
    key_date = stamp.strftime("%Y-%m-%d")

    def _compute():
        df = mo._daily(ticker)
        if df is None:
            return None
        dfn = _normalize_index(df)
        if dfn.shape[0] < 60:                       # reconstruct_flags needs ≥60 bars
            return None
        sc, vc = spy_close, vix_close
        if sc is None or vc is None:
            sc, vc = fetch_spy_vix()
        t0 = dfn.index[-1] if as_of is None else stamp
        return rr.reconstruct_flags(dfn, sc, vc, t0)

    if not use_cache:
        return _compute()
    return cache.get_or_compute(
        "live_factors", {"ticker": ticker, "date": key_date}, 900, _compute,
        should_cache=lambda r: r is not None)


def load_lift(path=LIFT_PATH) -> dict | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def lift_provenance_ok(lift: dict | None,
                       events_path: Path | None = None,
                       features_path: Path | None = None) -> bool:
    """True only if `lift` descends from the CURRENT sibling surge_events + surge_features AND
    records a present+numeric liquidity floor — the SAME fail-closed contract the retro consumers
    enforce (Codex r15: live_factors previously checked only the blocked bit, so a stale / cross-run
    / floor-less factor_lift could weight live flags against obsolete coefficients and publish an
    unblocked band). GRACEFUL (returns a bool; never raises) — this runs inside Streamlit pages, so
    any missing sibling / mismatch / absent floor ⇒ False ⇒ the caller blocks the band."""
    if not lift:
        return False
    # resolve the sibling paths at CALL time so the module globals can be redirected (tests / a
    # relocated dataset dir) — default-arg binding would freeze them at import.
    events_path = events_path or EVENTS_PATH
    features_path = features_path or FEATURES_PATH
    try:
        ev = json.loads(Path(events_path).read_text(encoding="utf-8")).get("generated_at")
        sf = json.loads(Path(features_path).read_text(encoding="utf-8")).get("generated_at")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    src = lift.get("source") or {}
    return bool(ev and sf
                and src.get("events_generated_at") == ev
                and src.get("features_generated_at") == sf
                and rfl.strict_floor(lift, "coverage", "liquidity_filter", "min_dollar_vol") is not None)


def _factor_weight(rec: dict) -> float:
    """Non-negative lift importance, support-shrunk: how much this factor counts
    toward the (lift-weighted) bull profile. Higher lift + more support → more
    weight. The band is then the matched fraction of this importance — it
    discriminates by how many AND how predictive the matched factors are, rather
    than collapsing when few factors clear lift>1 in a small, blocked sample.
    Contrarian factors (lift<1) carry little weight and are flagged by verdict in
    the scorecard rather than penalising the band."""
    lift = rec.get("lift")
    support = rec.get("support") or 0
    # numeric guard (Codex r20 round-4): a schema-drifted / forged row with a non-numeric lift or
    # support must not raise — treat it as zero weight rather than crash the page.
    if not isinstance(lift, (int, float)) or isinstance(lift, bool) or lift <= 0:
        return 0.0
    if not isinstance(support, (int, float)) or isinstance(support, bool):
        support = 0
    capped = min(float(lift), 1.0 + _LIFT_CAP)      # cap so one factor can't dominate
    confidence = support / (support + _SUPPORT_K)
    return capped * confidence


def match_archetypes(flags: dict) -> list[dict]:
    """Trader archetypes (retro_modules.json) this flag-set satisfies (tri-state)."""
    try:
        modules = json.loads(MODULES_PATH.read_text(encoding="utf-8")).get("modules", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    out = []
    for m in modules:
        if rm.module_match(flags, m) is True:
            out.append({"name": m.get("name"), "description": m.get("description", "")})
    return out


def score_surge(flags: dict | None, lift: dict | None = None,
                threshold: str = "ALL") -> dict | None:
    """Score live flags against the validated lift table → directional 傾向 band.

    band = lift-weighted coverage of MATCHED validated factors, over the factors we
    could actually evaluate for this ticker (None excluded from numerator AND
    denominator). NOT a probability. `blocked` inherits the canonical fail-closed
    gate — when True the band is directional-only."""
    if flags is None:
        return None
    lift = lift if lift is not None else load_lift()

    # PROVENANCE FIRST (Codex r20 round-4): a GARBAGE lift (stale/cross-run/floor-less/forged) may
    # also be schema-drifted — parsing its tables before the gate let a non-numeric lift raise in
    # _factor_weight and crash the page INSTEAD of showing the source lock. Gate first; garbage
    # returns the locked zero-field result WITHOUT traversing tables at all (round-3: zero at the
    # source so no caller can leak match counts / lift / verdict). archetypes stay (flags+config).
    prov_ok = bool(lift) and lift_provenance_ok(lift)
    _ev = {}
    if lift:
        try:
            _ev = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            _ev = {}
        # FORGE check (Codex r20 round-5) = assert_coverage_authoritative semantics, graceful: a
        # lift whose coverage self-reports UNBLOCKED while the AUTHORITATIVE surge_events imply
        # blocked is forged/drifted — GARBAGE, not merely directional. Without this, a same-run
        # floored forged-safe lift returned provenance_ok=True with real band/score/verdicts and
        # rendered as a directional band instead of the source lock.
        if prov_ok and rfl.events_implied_block(_ev) and not rfl.is_recommendations_blocked(lift):
            prov_ok = False
    if lift is not None and not prov_ok:
        return {
            "threshold": threshold,
            "score": 0.0, "band_level": 0, "band_label": _BAND_LABELS[0],
            "n_matched": 0, "n_validated": 0,
            "matched": [], "unmatched": [], "insufficient": [],
            "archetypes": match_archetypes(flags),
            "blocked": True,
            "provenance_ok": False,
            "caveat": _CAVEAT,
        }

    tables = (lift or {}).get("tables", {})
    table = tables.get(threshold) or tables.get("ALL") or {}
    recs = {r["factor"]: r for r in table.get("factors", []) if isinstance(r, dict) and "factor" in r}

    matched, unmatched, insufficient = [], [], []
    numer = denom = 0.0
    for fk, rec in recs.items():
        flag = flags.get(fk)
        entry = {"factor": fk, "dim": rec.get("dimension"),
                 "subfactor": rec.get("subfactor"), "desc": rec.get("desc"),
                 "lift": rec.get("lift"), "verdict": rec.get("verdict"),
                 "support": rec.get("support")}
        if flag is None:
            insufficient.append(entry)              # excluded from numer AND denom
            continue
        w = _factor_weight(rec)
        denom += w                                  # max achievable for this ticker
        if flag is True:
            numer += w
            matched.append(entry)
        else:
            unmatched.append(entry)

    score = max(0.0, min(1.0, numer / denom)) if denom > 0 else 0.0
    level = min(4, int(score * 5))                  # 0..4 → 很低..高
    # blocked = the canonical coverage gate OR the authoritative-events gate (Codex r15/r18): a
    # provenanced-but-survivorship/events-blocked lift keeps its REAL tables (directional band).
    blocked = True
    if lift:
        blocked = (rfl.is_recommendations_blocked(lift)
                   or rfl.events_implied_block(_ev))   # _ev read once above (round-5)
    return {
        "threshold": threshold,
        "score": round(score, 3),
        "band_level": level,
        "band_label": _BAND_LABELS[level],
        "n_matched": len(matched),
        "n_validated": len(recs),
        "matched": matched,
        "unmatched": unmatched,
        "insufficient": insufficient,
        "archetypes": match_archetypes(flags),
        "blocked": blocked,
        # provenance_ok distinguishes a GARBAGE lift (locked early-return above) from a merely
        # DIRECTIONAL one (survivorship/events-blocked but real tables). Codex r20: the batch UI
        # carries this so a force-blocked band can't rank as valid.
        "provenance_ok": prov_ok,
        "caveat": _CAVEAT,
    }


def checkup(ticker: str, as_of=None, spy_close=None, vix_close=None,
            threshold: str = "ALL", lift: dict | None = None) -> dict | None:
    """Convenience: flags + score in one call (for batch loops)."""
    flags = live_factor_flags(ticker, as_of, spy_close, vix_close)
    if flags is None:
        return None
    res = score_surge(flags, lift=lift, threshold=threshold)
    return {"ticker": ticker.upper().strip().lstrip("$"), "flags": flags, **(res or {})}


def main() -> int:
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
    flags = live_factor_flags(ticker, use_cache=False)
    if flags is None:
        print(f"[live_factors] no usable data for {ticker}", file=sys.stderr)
        return 1
    res = score_surge(flags)
    print(json.dumps({"ticker": ticker, "flags": flags, **res},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
