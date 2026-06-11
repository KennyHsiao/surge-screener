#!/usr/bin/env python3
"""Forward validation for the coiled-base lane — does the live edge hold up?

Forward accumulation REDUCES the retrospective's dominant bias (it can only score stocks
that already surged) by judging each signal on what happened AFTER it fired. It is NOT,
however, survivorship-free, and this harness does not pretend otherwise (Codex + adversarial
review): the scan universe is CURRENT index membership — a name that surged before it joined
the index is still counted — and any entry that has since DELISTED has no yfinance history,
so it drops out silently and its (often worst) outcome never reaches the EV. Both effects
bias the numbers OPTIMISTIC. The harness therefore reports `dropped_count` / `dropped_pct`
and a `survivorship` caveat so the reader can size the gap; a point-in-time `was_member`
gate is logged as future work, not silently assumed away.

Each daily scan (oversold_reversal_scan.py) drops a dated scan_*.json — those ARE the
forward snapshots. This reads only the CURRENT lane's snapshots (matched by lane_id),
de-dupes each (ticker, signal_date), enters at the signal close, follows every RESOLVED
entry forward, and reports — PER TIER (each tier carries its own PROVISIONAL/MATURE) — both:

  * the realized TOUCH hit-rate (did a Close ever reach +30/+40/+50% in the window?) with a
    Wilson interval — answers "do entries keep reaching the tier at the retro's prior?";
  * the strategy-level EXPECTED VALUE of actually trading the signal: enter at the signal
    close, hold to the window end, exit at that Close (a real, no-look-ahead rule — NOT the
    max, which assumes you sold the top). Mean = EV, plus median / win-rate / a normal-approx
    (exploratory) CI / a simple equity curve, AND ev_excess_vs_spy — but note that excess is
    a BETA=1 market adjustment (these are higher-beta names, so in an up-tape some "excess"
    is just beta); read it as a rough edge, not clean alpha.

An entry is RESOLVED only once its full forward window has elapsed AND its entry/horizon
closes are real (non-NaN); otherwise it is pending/dropped, never counted. EV is GROSS of
costs/slippage (the +30/20d tier churns weekly — several points of round-trip matter) and
the equity curve treats entries as one-at-a-time sequential trades (ignores overlap) — a
sanity curve, not a backtested P&L. The per-tier readouts are correlated and uncorrected
(exploratory). The lane's lift (2.39) was validated on sp500_pit; the forward scan default
is sp1500 — a universe-match flag flags the mismatch.

CLI:
    python scripts/oversold_reversal_forward.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "oversold_reversal"

import retro_factor_lift as rfl  # noqa: E402 — reuse the Wilson interval
import retro_reconstruct as rr   # noqa: E402 — reuse the cached OHLCV fetch
from oversold_reversal_scan import LANE_ID  # noqa: E402 — the CURRENT lane definition id

# (tier label, pct, window sessions) — must match retro_surge_label.DEFAULT_THRESHOLDS.
TIERS = [("+30%/20d", 0.30, 20), ("+40%/40d", 0.40, 40), ("+50%/60d", 0.50, 60)]
MIN_RESOLVED = 100  # below this the verdict stays PROVISIONAL


def evaluate_entry(close: np.ndarray, spy_close: np.ndarray) -> dict:
    """PURE (no I/O — unit-testable without network) per-tier outcome for one entry.

    `close[0]` / `spy_close[0]` are the entry-day Closes; index i is the i-th forward
    session, SPY date-aligned to the stock. Per tier returns:
      * resolved   — the window has elapsed AND close[0]/close[win] are real (non-NaN),
      * hit        — TOUCH: a Close in (0, win] reached +pct (optimistic / sold-the-top),
      * horizon_return     — REALIZED: close[win]/close[0] - 1 (hold-to-window-end exit),
      * spy_horizon_return — SPY over the SAME entry→win span,
      * excess_return      — horizon_return - spy_horizon_return (BETA=1 market adjustment).
    Touch is reported even when unresolved (it can only become true with more data);
    horizon/excess are None until resolved so EV never counts a half-formed/NaN window."""
    base = float(close[0]) if close.size else float("nan")
    spy_base = float(spy_close[0]) if spy_close.size else float("nan")
    out: dict[str, dict] = {}
    for label, pct, win in TIERS:
        seg = close[1:win + 1]
        # nanmax (not max): a mid-window NaN (corp action / halt) must NOT mask a real +pct
        # touch that already happened earlier in the window (ultrareview). all-NaN ⇒ nan ⇒ no touch.
        seg_hi = float(np.nanmax(seg)) if seg.size and np.any(np.isfinite(seg)) else float("nan")
        touch = bool(np.isfinite(base) and base > 0
                     and np.isfinite(seg_hi) and seg_hi / base - 1.0 >= pct)
        # RESOLVED = the STOCK's window has fully elapsed AND both endpoints are real, so a
        # genuine realized horizon return exists. Independent of the baseline (a missing SPY
        # tail must not throw away a real return). The close[win] finiteness check stops a
        # mid-window data gap (source emits NaN, not a dropped row) from resolving True and
        # poisoning EV with a NaN (adversarial review: "NaN at win-th resolves True").
        resolved = bool((len(close) - 1) >= win and np.isfinite(base) and base > 0
                        and np.isfinite(close[win]))
        # BASELINE is a SEPARATE gate: SPY must actually have a non-NaN Close at BOTH the
        # entry and the +win horizon. _resolve reindexes SPY WITHOUT ffill, so a missing SPY
        # tail arrives here as NaN (not a silently stale forward-fill). The old length guard
        # was a NO-OP in the real path — reindex forces len(spy_close)==len(close) — so a
        # short/stale SPY tail would have inflated excess. Check finiteness, not length.
        # (Codex stop-time review: "SPY tail guard is bypassed in the real resolver".)
        baseline_ok = bool(resolved and (len(spy_close) - 1) >= win
                           and np.isfinite(spy_base) and spy_base > 0
                           and np.isfinite(spy_close[win]))
        hz = (float(close[win]) / base - 1.0) if resolved else None
        if baseline_ok:
            spy_hz = float(spy_close[win]) / spy_base - 1.0
            excess = hz - spy_hz
        else:
            spy_hz = excess = None
        out[label] = {"resolved": resolved, "baseline_ok": baseline_ok, "hit": touch,
                      "horizon_return": hz, "spy_horizon_return": spy_hz,
                      "excess_return": excess}
    return out


def _mean_block(xs: list[float]) -> dict:
    """Mean (EV) + median + win-rate + a normal-approx 90% CI on the mean. Pure."""
    n = len(xs)
    if n == 0:
        return {"n": 0, "ev": None, "median": None, "win_rate": None,
                "ci90": [None, None], "std": None}
    arr = np.asarray(xs, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    half = 1.645 * std / (n ** 0.5) if n > 1 else 0.0   # z₀.₀₅, normal approx (labelled)
    return {"n": n, "ev": round(mean, 4), "median": round(float(np.median(arr)), 4),
            "win_rate": round(float((arr > 0).mean()), 4),
            "ci90": [round(mean - half, 4), round(mean + half, 4)],
            "std": round(std, 4)}


def _aggregate_tier(resolved_rows: list[dict], label: str,
                    min_resolved: int | None = None) -> dict:
    """PURE aggregation for one tier over the resolved entries (each row carries
    `entry_date` + `tiers[label]`). Touch hit-rate (Wilson) + EV/excess (mean blocks) +
    a one-trade-at-a-time equity curve ordered by entry_date.

    MATURITY GATE (Codex C-8 review): the strategy fields (EV / excess / CI / equity) are
    PUBLISHED ONLY at resolved >= min_resolved — the PROVISIONAL verdict was previously just a
    LABEL while the artifact still carried a 1-99-trade EV that a consumer could read as a
    strategy result (underpowered + survivorship-biased = fail-open). Counts + touch hit-rate
    stay visible (the honest accumulation progress); the strategy fields are None/[] until
    the tier matures. `mature` is the machine-readable gate.

    EXCESS gates SEPARATELY (Codex C-8 round-3): the SPY-excess block is computed over the
    baseline-OK subset (excess_n ≤ resolved — _resolve keeps stock EV resolved when SPY is
    missing), so 100 stock-resolved rows with 1 valid baseline row would otherwise publish an
    underpowered excess EV/CI under mature:true. excess fields require excess_n >= min_resolved
    (`excess_mature`)."""
    if min_resolved is None:
        min_resolved = MIN_RESOLVED
    res = [r for r in resolved_rows if r["tiers"][label]["resolved"]]
    n = len(res)
    hits = sum(1 for r in res if r["tiers"][label]["hit"])
    lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)
    mature = n >= min_resolved

    # Resolved ⇒ horizon_return is always present; excess only for the baseline-OK subset
    # (SPY had a valid Close at entry + horizon), so it is filtered + counted separately.
    hz = [r["tiers"][label]["horizon_return"] for r in res]
    ex = [r["tiers"][label]["excess_return"] for r in res
          if r["tiers"][label]["excess_return"] is not None]
    ev = _mean_block(hz)
    exb = _mean_block(ex)

    ordered = sorted(res, key=lambda r: r.get("entry_date") or "")
    equity, curve = 1.0, []
    for r in ordered:
        equity *= 1.0 + r["tiers"][label]["horizon_return"]
        curve.append([r.get("entry_date"), round(equity, 4)])

    excess_mature = exb["n"] >= min_resolved
    return {
        "resolved": n, "hits": hits,
        "hit_rate": round(hits / n, 4) if n else None,
        "wilson90": [round(lo, 4), round(hi, 4)],
        "mature": mature,
        "excess_mature": excess_mature,
        "ev_horizon": ev["ev"] if mature else None,
        "median_horizon": ev["median"] if mature else None,
        "win_rate_horizon": ev["win_rate"] if mature else None,
        "ev_horizon_ci90": ev["ci90"] if mature else None,
        "ev_excess_vs_spy": exb["ev"] if excess_mature else None,
        "excess_n": exb["n"],
        "excess_win_rate": exb["win_rate"] if excess_mature else None,
        "ev_excess_ci90": exb["ci90"] if excess_mature else None,
        "equity_multiple": round(equity, 4) if (n and mature) else None,
        "equity_curve": curve if mature else [],
    }


def _collect_entries() -> list[dict]:
    """One entry per (ticker, signal_date) — ONLY this lane's snapshots (module=coiled_base),
    so the hit-rate never matures on a MIXED population (the dir may still hold legacy
    volume_ignition scans). Entry date = the candidate's `signal_date` (the actual signal
    close), NOT the file `as_of_date` — a weekend/holiday scan would otherwise enter a
    session late and corrupt the realized gain."""
    seen: dict[tuple, dict] = {}
    for f in sorted(OUT_DIR.glob("scan_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Isolate by the EXACT lane definition (lane_id), not the coarse `module` — so a
        # future gate change (lane_id v2) with the same module never mixes into this
        # population. Legacy scans (no lane_id) are excluded.
        if d.get("lane_id") != LANE_ID:
            continue
        for c in d.get("candidates", []):
            sdate = c.get("signal_date") or c.get("as_of") or d.get("as_of_date")
            key = (c["ticker"], sdate)
            entry = {"ticker": c["ticker"], "entry_date": sdate,   # enter at the signal close
                     "entry_price": c.get("last_price")}
            if key not in seen or (entry["entry_date"] or "") < (seen[key]["entry_date"] or ""):
                seen[key] = entry
    return list(seen.values())


_SPY_CACHE: dict[str, pd.Series | None] = {}


def _spy_close() -> pd.Series | None:
    """SPY Close indexed by normalized date, fetched once (the market baseline)."""
    if "spy" not in _SPY_CACHE:
        df = rr._hist_auto_adjust_false("SPY", "2y")
        if df is not None:
            df = df.copy()
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            _SPY_CACHE["spy"] = df["Close"]
        else:
            _SPY_CACHE["spy"] = None
    return _SPY_CACHE["spy"]


def _resolve(entry: dict) -> dict | None:
    """Follow one entry forward; return per-tier outcomes (via the pure evaluate_entry),
    or None if prices/date are unavailable (delisted ⇒ yfinance None ⇒ dropped — see the
    survivorship accounting in main()). SPY is date-aligned to the stock's forward sessions
    so the +win horizon is the SAME calendar span for both legs."""
    ed = pd.to_datetime(entry.get("entry_date"), errors="coerce")
    if pd.isna(ed):          # malformed / legacy / hand-edited entry_date — don't crash
        return None
    ed = ed.normalize()
    df = rr._hist_auto_adjust_false(entry["ticker"], "2y")
    if df is None:
        return None
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    fwd = df[df.index >= ed]
    if len(fwd) < 1:
        return None
    # The 2y fetch window can START AFTER an old entry_date; then fwd[0] is the window's first
    # session (≈2y after entry), NOT the entry day, and base would be the wrong price. Drop the
    # entry (counts as dropped) rather than silently measuring against a bogus base (ultrareview).
    if fwd.index[0] > ed + pd.Timedelta(days=7):
        return None
    base = float(fwd["Close"].iloc[0])
    if base <= 0:
        return None
    # A transient SPY fetch failure must NOT wipe every entry + mislabel the cause as delisting
    # (the survivorship caveat). Pass an EMPTY baseline instead: evaluate_entry still resolves
    # touch + horizon EV, only voiding the β=1 excess (baseline_ok=False) — ultrareview.
    spy = _spy_close()
    if spy is None:
        spy_close = np.array([], dtype=float)
        return {"ticker": entry["ticker"], "entry_date": entry["entry_date"],
                "tiers": evaluate_entry(fwd["Close"].to_numpy(dtype=float), spy_close)}
    # Reindex SPY to the stock's forward dates WITHOUT ffill: a date SPY lacks (e.g. a short
    # data tail) stays NaN so evaluate_entry's baseline gate can reject it, rather than being
    # back-filled with a stale Close that would corrupt excess (Codex stop-time review).
    spy_fwd = spy.reindex(fwd.index)  # SPY Close on each stock-forward date (NaN if missing)
    close = fwd["Close"].to_numpy(dtype=float)
    spy_close = spy_fwd.to_numpy(dtype=float)
    return {"ticker": entry["ticker"], "entry_date": entry["entry_date"],
            "tiers": evaluate_entry(close, spy_close)}


def main() -> int:
    entries = _collect_entries()
    resolved_rows = [r for r in (_resolve(e) for e in entries) if r is not None]

    by_tier = {label: _aggregate_tier(resolved_rows, label) for label, _p, _w in TIERS}
    # Per-tier verdict — each tier matures on ITS OWN resolved count, so a fast +30/20d tier
    # can't flip the slow +50/60d tier to MATURE (adversarial review). Global verdict is the
    # CONSERVATIVE min across tiers, not the max.
    verdict_by_tier = {label: ("MATURE" if t["resolved"] >= MIN_RESOLVED else "PROVISIONAL")
                       for label, t in by_tier.items()}
    min_resolved = min((t["resolved"] for t in by_tier.values()), default=0)

    # Survivorship accounting — entries we could NOT follow forward (delisted ⇒ no yfinance
    # history, bad date, no forward sessions) are dropped from EV. The dropped names are often
    # the worst outcomes, so a high dropped_pct means EV is biased optimistic. Disclose it.
    dropped = len(entries) - len(resolved_rows)
    dropped_pct = round(dropped / len(entries), 4) if entries else None

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "coiled_base",
        "lane_id": LANE_ID,
        "entries_accumulated": len(entries),
        "price_resolvable": len(resolved_rows),
        "dropped_count": dropped,
        "dropped_pct": dropped_pct,
        "min_resolved_across_tiers": min_resolved,
        "min_resolved_for_verdict": MIN_RESOLVED,
        "verdict": ("PROVISIONAL — sample below threshold, indicative only"
                    if min_resolved < MIN_RESOLVED else "MATURE"),
        "verdict_by_tier": verdict_by_tier,
        "survivorship": {
            "survivorship_free": False,
            "forward_universe": "current index membership (sp1500 live members at scan time)",
            "validated_universe": "sp500_pit",
            "universe_match": False,
            "caveats": [
                "Current-membership scan counts a name that surged BEFORE it joined the index.",
                "Delisted names have no yfinance history → dropped (see dropped_pct); their "
                "outcomes (often the worst) never reach EV → EV biased optimistic.",
                "A point-in-time was_member(ticker, entry_date) gate is future work.",
            ],
        },
        "ev_caveats": [
            "ev_excess_vs_spy is a BETA=1 adjustment; these are higher-beta names, so some "
            "'excess' is beta, not alpha. Treat as a rough edge, not clean alpha.",
            "EV is GROSS of costs/slippage (the +30/20d tier churns weekly — round-trip matters).",
            "ev_*_ci90 is a normal-approx CI; single-stock returns are right-skewed/outlier-driven "
            "(exploratory, not a bootstrap). The per-tier readouts are correlated and uncorrected.",
            "equity_curve compounds entries one-at-a-time in entry-date order (ignores overlap) "
            "— a sanity curve, not a backtested P&L.",
        ],
        "note": "(1) TOUCH hit-rate (a Close reached +pct — optimistic, sold-the-top; Wilson "
                "CI). (2) STRATEGY EV: enter at the signal close, hold to window end, exit at "
                "that Close (no look-ahead). See survivorship + ev_caveats above; the lane "
                "gates on the runway-INDEPENDENT pair bb_squeeze & rsi_40_65 (lane_runway_check). "
                "⚠ Pre-rewrite scans were the OLD rvol+oversold lane — clear scan_*.json for a "
                "clean baseline.",
        "by_tier": by_tier,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "validation_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[oversold-fwd] {len(entries)} entries, {len(resolved_rows)} price-resolvable, "
          f"{dropped} dropped ({dropped_pct}) → {payload['verdict']} "
          f"(survivorship NOT free — see dropped_pct)")
    for label, t in by_tier.items():
        print(f"  {label} [{verdict_by_tier[label]}]: touch {t['hits']}/{t['resolved']} "
              f"(rate {t['hit_rate']}, 90% CI {t['wilson90']}) | "
              f"EV {t['ev_horizon']} gross (excess≈SPY[β=1] {t['ev_excess_vs_spy']} "
              f"n={t['excess_n']}, win {t['win_rate_horizon']}, eq×{t['equity_multiple']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
