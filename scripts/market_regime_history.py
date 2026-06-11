#!/usr/bin/env python3
"""History Analysis corpus for the 大盤行情研判 agent — labelled past ^GSPC/VIX regimes (design v7, P1).

The DEoT "History Analysis (主動檢索)" source: PURE, deterministic, VERIFIED data (no LLM). Fetch ~20y of
^GSPC + ^VIX (multi-cycle — must span the 2008 / 2018-Q4 / 2020 / 2022 bears, NOT a bull-only 5y window),
label each session rally / correction / range, attach the REALIZED forward ^GSPC return AND max-drawdown at
20/40/60 sessions, and expose retrieve_regime_analogs() so the agent cites real precedent ("in the past
sessions that looked like today, what did the index actually do — and how deep was the drawdown?").

De-biasing (Codex design review): tail metrics (forward MDD, p10, worst) sit alongside the mean so a
"correction" analog can't read as gentle mean-reversion; and the 看空 ANALOG claim is FAIL-CLOSED behind an
episode-based floor (≥ distinct correction episodes + non-overlapping windows) so one prolonged bear can't
masquerade as a robust precedent. Benchmark is ^GSPC (the resolution-contract benchmark) for consistency.

Heuristic regime labels (EXPLORATORY — a coarse tag, NOT a signal):
  rally       close > 50DMA AND > 200DMA AND VIX < 20      (uptrend, calm)
  correction  close < 200DMA AND VIX >= 22                  (downtrend + fear)
  range       everything else                              (mixed / choppy)

CLI:  python scripts/market_regime_history.py [--period 20y]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import retro_reconstruct as rr                      # noqa: E402 — cached OHLCV fetch
from oversold_reversal_forward import _mean_block   # noqa: E402 — pure mean/median/win/CI block

OUT_DIR = REPO / "reports" / "market_thesis"
FWD = [20, 40, 60]            # forward session windows (short / mid / long), aligned to the 期程 buckets
REGIMES = ("rally", "correction", "range")
# Episode-based bearish-analog floor (de-bias gate). Config-able; raw session counts are telemetry only.
EP_DRAWDOWN = 0.10            # a correction episode needs ≥10% peak→trough drawdown
MIN_BEAR_EPISODES = 3         # ≥3 DISTINCT correction episodes…
MIN_BEAR_SPAN_YEARS = 2.0     # …spanning ≥2 calendar years…
BEARISH_FLOOR = 10            # …AND ≥10 NON-OVERLAPPING matured windows (≥H sessions apart) per bucket.
# The ONLY VIX buckets accepted as a 看空 matched key. "unknown" (the _vix_bucket sentinel when VIX is
# missing/non-finite) is deliberately EXCLUDED — a failed VIX fetch must fail the gate, not match it.
CONCRETE_VIX_BUCKETS = ("low", "normal", "elevated", "panic")
MIN_CORPUS_SPAN_YEARS = 15.0  # publish gate: the corpus must span ≥15y (multi-cycle, v7 §1b) or we refuse
MAX_UNKNOWN_VIX_RATE = 0.01   # publish gate: >1% sessions with vix_bucket="unknown" ⇒ the VIX leg degraded —
                              # rally/correction need VIX, so a dead VIX feed silently mislabels bears as "range"
MAX_VIX_STALE_SESSIONS = 5    # a session whose last RAW VIX print is older than this is VIX-MISSING ("unknown");
                              # measured BEFORE ffill so one early print can't masquerade as full coverage (r7)
MAX_UNKNOWN_VIX_RUN = 10      # longest tolerated CONSECUTIVE unknown stretch — a concentrated outage must not
                              # hide under the 1% aggregate rate (r8); and the LATEST row must always be concrete
# v7 §1b pins the multi-cycle guarantee to NAMED bears — the publish gate must verify a closed episode's
# TROUGH falls inside each window (span+count alone let a 2011-onward corpus skip the GFC, Codex r9).
# Future maintainers: extend with newer bears; never drop one to make a truncated fetch pass.
REQUIRED_BEAR_WINDOWS = {
    "GFC_2008":   ("2008-01-01", "2009-12-31"),
    "Q4_2018":    ("2018-09-01", "2019-01-31"),
    "COVID_2020": ("2020-02-01", "2020-05-31"),
    "BEAR_2022":  ("2022-01-01", "2022-12-31"),
}


def _vix_bucket(vix: float | None) -> str:
    if vix is None or not np.isfinite(vix):
        return "unknown"
    if vix < 15:
        return "low"
    if vix < 20:
        return "normal"
    if vix < 30:
        return "elevated"
    return "panic"


def label_regime(close: float, ma50: float | None, ma200: float | None, vix: float | None) -> str:
    """Coarse 3-state market regime (deterministic, exploratory)."""
    above50 = bool(ma50 is not None and np.isfinite(ma50) and close > ma50)
    above200 = bool(ma200 is not None and np.isfinite(ma200) and close > ma200)
    v = vix if (vix is not None and np.isfinite(vix)) else None
    if (ma200 is not None and np.isfinite(ma200) and close < ma200) and (v is not None and v >= 22):
        return "correction"
    if above50 and above200 and (v is not None and v < 20):
        return "rally"
    return "range"


def label_episodes(close: pd.Series, ep_drawdown: float = EP_DRAWDOWN) -> list[dict]:
    """Deterministic correction-episode segmentation (design v7 §1b). An episode spans a running-peak to its
    FIRST FULL RECLAIM (close ≥ peak) and QUALIFIES iff its max peak→trough drawdown ≥ ep_drawdown. A <10% dip
    that reclaims is no episode (peak just advances); a prolonged unrecovered bear stays ONE episode (no 50%
    split); a trailing qualifying drop with no reclaim is `ongoing`. episode_id = trough date (ISO)."""
    vals = close.to_numpy(float)
    idx = close.index
    n = len(vals)
    eps: list[dict] = []
    if n == 0:
        return eps

    def _mk(pi, ti, ei, ongoing=False):
        peak, trough = float(vals[pi]), float(vals[ti])
        return {"episode_id": idx[ti].date().isoformat(),
                "start": idx[pi].date().isoformat(), "trough": idx[ti].date().isoformat(),
                "end": idx[ei].date().isoformat(), "ongoing": ongoing,
                "drawdown_pct": round(trough / peak - 1.0, 4) if peak > 0 else None,
                "peak_close": round(peak, 2), "trough_close": round(trough, 2),
                "start_i": int(pi), "end_i": int(ei)}

    peak = vals[0]; peak_i = 0; trough = vals[0]; trough_i = 0; in_ep = False
    for i in range(1, n):
        p = vals[i]
        if p < peak:
            in_ep = True
            if p < trough:
                trough = p; trough_i = i
        else:  # full reclaim / new high
            if in_ep and peak > 0 and (peak - trough) / peak >= ep_drawdown:
                eps.append(_mk(peak_i, trough_i, i))
            peak = p; peak_i = i; trough = p; trough_i = i; in_ep = False
    if in_ep and peak > 0 and (peak - trough) / peak >= ep_drawdown:
        eps.append(_mk(peak_i, trough_i, n - 1, ongoing=True))
    return eps


def _gspc_vix(period: str) -> tuple[pd.Series, pd.Series] | None:
    gspc = rr._hist_auto_adjust_false("^GSPC", period)
    vixdf = rr._hist_auto_adjust_false("^VIX", period)
    if gspc is None or vixdf is None:
        return None
    sc = gspc["Close"].dropna()
    vc = vixdf["Close"].dropna()
    sc.index = pd.to_datetime(sc.index).tz_localize(None).normalize()
    vc.index = pd.to_datetime(vc.index).tz_localize(None).normalize()
    return sc, vc


def _fwd_mdd(close: np.ndarray, i: int, w: int) -> float | None:
    """Max drawdown an entrant at i would suffer over the next w sessions (most-negative close/peak−1)."""
    if i + w >= len(close) or close[i] <= 0:
        return None
    seg = close[i:i + w + 1]
    runmax = np.maximum.accumulate(seg)
    dd = seg / runmax - 1.0
    return round(float(dd.min()), 4)


def build_daily(period: str = "20y", sv: tuple | None = None) -> list[dict]:
    """One record per session: regime + VIX bucket + episode_id + realized forward returns AND forward MDD.
    `sv` lets the caller inject an already-fetched (close, vix) pair so a transient SECOND fetch can't
    silently swap in a different/empty dataset (Codex r5)."""
    if sv is None:
        sv = _gspc_vix(period)
    if sv is None:
        return []
    spy, vix = sv
    # RAW availability BEFORE ffill (Codex r7): ffill makes one early VIX print look like full coverage, so
    # staleness must be measured on the raw reindexed series. A session whose last real VIX print is more
    # than MAX_VIX_STALE_SESSIONS ago is treated as VIX-MISSING (v=None ⇒ vix_bucket="unknown") — the
    # corpus unknown-rate gate and the bearish concrete-bucket gate then both refuse it. Small calendar
    # gaps (holidays / brief outages) within the tolerance are still ffilled as before.
    vix_raw = vix.reindex(spy.index)
    raw_finite = np.isfinite(vix_raw.to_numpy(float))
    vix = vix_raw.ffill()
    ma50 = spy.rolling(50).mean()
    ma200 = spy.rolling(200).mean()
    close = spy.to_numpy(float)
    n = len(close)
    vix_age = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)  # sessions since last raw VIX print
    last = -1
    for i in range(n):
        if raw_finite[i]:
            last = i
        if last >= 0:
            vix_age[i] = i - last

    # episode membership: tag each session with the correction episode whose [start_i, end_i] covers it.
    eps = label_episodes(spy)
    ep_of = {}
    for e in eps:
        for j in range(e["start_i"], e["end_i"] + 1):
            ep_of[j] = e["episode_id"]

    rows: list[dict] = []
    for i in range(n):
        if i < 200:  # need a full 200DMA warmup before the label means anything
            continue
        c = float(close[i])
        v = (float(vix.iloc[i])
             if np.isfinite(vix.iloc[i]) and vix_age[i] <= MAX_VIX_STALE_SESSIONS else None)
        regime = label_regime(c, float(ma50.iloc[i]), float(ma200.iloc[i]), v)
        rec = {"date": spy.index[i].date().isoformat(), "sess_i": i, "close": round(c, 2),
               "vix": round(v, 2) if v is not None else None, "vix_bucket": _vix_bucket(v),
               "regime": regime, "episode_id": ep_of.get(i),
               "spy_vs_50dma": "above" if c > float(ma50.iloc[i]) else "below",
               "spy_vs_200dma": "above" if c > float(ma200.iloc[i]) else "below"}
        for w in FWD:
            rec[f"fwd_{w}d"] = (float(close[i + w]) / c - 1.0) if (i + w) < n and c > 0 else None
            rec[f"fwd_mdd_{w}d"] = _fwd_mdd(close, i, w)
        rows.append(rec)
    return rows


def _fwd_block(rows: list[dict], window: int) -> dict:
    """Forward-return distribution + TAIL metrics for one window over rows (mean alone hides bear pain)."""
    vals = [r[f"fwd_{window}d"] for r in rows if r.get(f"fwd_{window}d") is not None]
    mdds = [r[f"fwd_mdd_{window}d"] for r in rows if r.get(f"fwd_mdd_{window}d") is not None]
    blk = _mean_block(vals)
    arr = np.asarray(vals, float)
    out = {"resolved": blk["n"], "mean": blk["ev"], "median": blk["median"],
           "up_rate": blk["win_rate"], "ci90": blk["ci90"],
           "p10": round(float(np.percentile(arr, 10)), 4) if arr.size else None,
           "worst": round(float(arr.min()), 4) if arr.size else None,
           "mean_mdd": round(float(np.mean(mdds)), 4) if mdds else None,
           "worst_mdd": round(float(np.min(mdds)), 4) if mdds else None}
    return out


def summarize(daily: list[dict]) -> dict:
    out = {}
    for reg in REGIMES:
        rrows = [r for r in daily if r["regime"] == reg]
        out[reg] = {"days": len(rrows), **{f"fwd_{w}d": _fwd_block(rrows, w) for w in FWD}}
    return out


def regime_runs(daily: list[dict]) -> list[dict]:
    """Collapse consecutive same-regime sessions into runs (human-readable context; distinct from the
    drawdown EPISODES used by the bearish floor)."""
    runs: list[dict] = []
    for r in daily:
        if runs and runs[-1]["regime"] == r["regime"]:
            runs[-1]["end"] = r["date"]; runs[-1]["sessions"] += 1; runs[-1]["end_close"] = r["close"]
        else:
            runs.append({"regime": r["regime"], "start": r["date"], "end": r["date"],
                         "sessions": 1, "start_close": r["close"], "end_close": r["close"]})
    for e in runs:
        e["ret_pct"] = round(e["end_close"] / e["start_close"] - 1.0, 4) if e["start_close"] else None
    return runs


def _nonoverlap_count(sess_indices: list[int], w: int) -> int:
    """Greedy count of windows ≥ w sessions apart (independence guard against autocorrelated samples)."""
    cnt, last = 0, None
    for s in sorted(sess_indices):
        if last is None or (s - last) >= w:
            cnt += 1; last = s
    return cnt


def corpus_inadequacy(daily: list[dict], eps: list[dict]) -> str | None:
    """PURE publish gate (Codex r5): reason string if the corpus is empty / short / not multi-cycle, else
    None. An inadequate corpus must NEVER be published — downstream bearish suppression would read as
    legitimate insufficient analogs while rally/range analogs silently used the biased window."""
    if not daily:
        return "empty_daily"
    span_years = ((pd.to_datetime(daily[-1]["date"]) - pd.to_datetime(daily[0]["date"])).days / 365.25)
    if span_years < MIN_CORPUS_SPAN_YEARS:
        return f"span_{span_years:.1f}y<min{MIN_CORPUS_SPAN_YEARS:.0f}y"
    closed = [e for e in eps if not e.get("ongoing")]
    if len(closed) < MIN_BEAR_EPISODES:
        return f"closed_correction_episodes_{len(closed)}<min{MIN_BEAR_EPISODES}"
    # NAMED-cycle coverage (Codex r9+r10): each required bear window must contain a closed episode's trough,
    # AND that trough must survive into the PUBLISHED corpus — build_daily drops the first 200 warmup
    # sessions, so a late-2008 fetch can hold a GFC trough in eps that no daily row actually covers (r10).
    # ISO strings compare lexically, so plain string comparison is correct here.
    first_pub, last_pub = daily[0]["date"], daily[-1]["date"]
    troughs = [e.get("trough") for e in closed
               if e.get("trough") and first_pub <= e["trough"] <= last_pub]
    missing_bears = [name for name, (lo, hi) in REQUIRED_BEAR_WINDOWS.items()
                     if not any(lo <= t <= hi for t in troughs)]
    if missing_bears:
        return "missing_required_bears:" + ",".join(missing_bears)
    # VIX-leg coverage (Codex r6-r8): an empty/truncated/stale VIX fetch mislabels regimes BEFORE the bearish
    # floor ever runs. Three checks, none of which may hide behind another:
    buckets = [r.get("vix_bucket") for r in daily]
    # (r8) the LATEST row is what the forecaster reads for "today" — a current outage (even 1 session past
    # the stale tolerance) must refuse, no matter how clean the 20y aggregate looks.
    if buckets[-1] not in CONCRETE_VIX_BUCKETS:
        return "latest_vix_unknown_or_stale"
    # (r8) a CONCENTRATED outage (e.g. a 30-session dead window ≈0.6% of 20y) must not hide under the
    # aggregate-rate threshold — cap the longest consecutive unknown stretch.
    run = longest = 0
    for b in buckets:
        run = run + 1 if b not in CONCRETE_VIX_BUCKETS else 0
        longest = max(longest, run)
    if longest > MAX_UNKNOWN_VIX_RUN:
        return f"unknown_vix_run_{longest}>max{MAX_UNKNOWN_VIX_RUN}"
    # (r6) broad degradation: more than a sliver of all sessions lacking a concrete bucket.
    unknown_rate = sum(1 for b in buckets if b not in CONCRETE_VIX_BUCKETS) / len(daily)
    if unknown_rate > MAX_UNKNOWN_VIX_RATE:
        return f"unknown_vix_rate_{unknown_rate:.2%}>max{MAX_UNKNOWN_VIX_RATE:.0%}"
    return None


def retrieve_regime_analogs(daily: list[dict], regime: str, vix_bucket: str | None = None,
                            k: int = 5) -> dict:
    """REAL historical precedent for today's regime. For 看空 (regime='correction') the analog claim is
    FAIL-CLOSED behind an EPISODE-based floor: ≥ MIN_BEAR_EPISODES distinct correction episodes spanning
    ≥ MIN_BEAR_SPAN_YEARS, AND ≥ BEARISH_FLOOR non-overlapping matured windows per bucket — else that window
    returns `insufficient_bearish_analogs` (no precedent claim; the FORECAST is not blocked, only the analog
    reasoning). Raw session counts are telemetry only. Never invents analogs."""
    all_bucket = [r for r in daily if r["regime"] == regime]
    # VIX bucket is part of the matched KEY — ALWAYS filter (fail-closed). A thin bucket simply fails the
    # floor below; we NEVER widen back to the full pool to unlock (that was a fail-OPEN bug). The all-bucket
    # count is telemetry ONLY, never an unlock path.
    pool = [r for r in all_bucket if r["vix_bucket"] == vix_bucket] if vix_bucket else all_bucket

    out = {"regime": regime, "vix_bucket": vix_bucket, "n_sessions": len(pool),
           "all_bucket_sessions": len(all_bucket)}
    is_bear = regime == "correction"
    if is_bear:
        # ALL-POOL counts are TELEMETRY ONLY — never the unlock path. The floor is gated per-horizon on the
        # MATURED rows below, so an unresolved episode (fwd=None) can't pad the distinct-episode count.
        all_eps = {r["episode_id"] for r in pool if r.get("episode_id")}
        all_dates = sorted(r["date"] for r in pool)
        all_span = ((pd.to_datetime(all_dates[-1]) - pd.to_datetime(all_dates[0])).days / 365.25) if all_dates else 0.0
        out["bear_telemetry"] = {"all_pool_distinct_episodes": len(all_eps),
                                 "all_pool_span_years": round(all_span, 1), "raw_sessions": len(pool)}

    suppressed_any = False
    for w in FWD:
        matured = [r for r in pool if r.get(f"fwd_{w}d") is not None]
        if is_bear and vix_bucket not in CONCRETE_VIX_BUCKETS:
            # the 看空 matched KEY REQUIRES a CONCRETE VIX bucket (v7 §1b). None/empty must not read the full
            # correction pool, and the truthy "unknown" sentinel (_vix_bucket() when the live VIX fetch fails)
            # must not be treated as a matched key either — fail closed on anything non-concrete (Codex r4).
            suppressed_any = True
            out[f"fwd_{w}d"] = {"status": "insufficient_bearish_analogs", "reason": "missing_vix_bucket"}
            continue
        if is_bear:
            # episodes/span/non-overlap are ALL computed from the MATURED rows for THIS horizon — a row whose
            # forward window hasn't elapsed contributes neither a window nor a distinct episode (Codex fix).
            m_eps = {r["episode_id"] for r in matured if r.get("episode_id")}
            m_dates = sorted(r["date"] for r in matured)
            m_span = ((pd.to_datetime(m_dates[-1]) - pd.to_datetime(m_dates[0])).days / 365.25) if m_dates else 0.0
            nonov = _nonoverlap_count([r["sess_i"] for r in matured], w)
            ok = (len(m_eps) >= MIN_BEAR_EPISODES and m_span >= MIN_BEAR_SPAN_YEARS
                  and nonov >= BEARISH_FLOOR)
            if not ok:
                suppressed_any = True
                out[f"fwd_{w}d"] = {"status": "insufficient_bearish_analogs",
                                    "matured_episodes": len(m_eps), "matured_span_years": round(m_span, 1),
                                    "nonoverlap_n": nonov,
                                    "required": {"episodes": MIN_BEAR_EPISODES,
                                                 "span_years": MIN_BEAR_SPAN_YEARS,
                                                 "nonoverlap": BEARISH_FLOOR}}
                continue
        out[f"fwd_{w}d"] = _fwd_block(matured, w)
    if is_bear:
        out["bearish_analog_suppressed"] = suppressed_any

    # Dated 歷史前例 examples are themselves analog material — for 看空 they are SUPPRESSED whenever the
    # bearish floor failed for any window (else a renderer could cite precedent while the stats say
    # insufficient). Only emitted once the gate passes (or for non-correction regimes).
    if is_bear and suppressed_any:
        out["examples"] = []
        out["examples_suppressed"] = "insufficient_bearish_analogs"
    else:
        examples = [r for r in pool if r.get("fwd_60d") is not None]
        examples.sort(key=lambda r: r["date"], reverse=True)
        out["examples"] = [{"date": r["date"], "vix": r["vix"], "episode_id": r.get("episode_id"),
                            "fwd_20d": r["fwd_20d"], "fwd_60d": r["fwd_60d"],
                            "fwd_mdd_60d": r.get("fwd_mdd_60d")} for r in examples[:k]]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Label past ^GSPC/VIX market regimes (History Analysis corpus)")
    ap.add_argument("--period", default="20y", help="yfinance lookback; ≥~19y to span the 2008 bear")
    ap.add_argument("--output", default=str(OUT_DIR / "regime_history.json"))
    args = ap.parse_args()

    sv = _gspc_vix(args.period)
    if sv is None:
        print("[regime-hist] no ^GSPC/^VIX history fetched", file=sys.stderr)
        return 1
    daily = build_daily(args.period, sv=sv)   # reuse the validated fetch — no silent second-fetch swap
    eps = label_episodes(sv[0])
    inadequate = corpus_inadequacy(daily, eps)
    if inadequate:
        print(f"[regime-hist] REFUSING to publish an inadequate corpus: {inadequate} "
              f"(an empty/short/bull-only window would masquerade as legitimate insufficient analogs)",
              file=sys.stderr)
        return 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": "^GSPC", "vix": "^VIX", "lookback_period": args.period,
        "rules": {"rally": "close>50DMA & >200DMA & VIX<20", "correction": "close<200DMA & VIX>=22",
                  "range": "otherwise", "vix_buckets": "low<15 normal<20 elevated<30 panic>=30",
                  "episode": f"peak→full-reclaim, qualifies if drawdown≥{EP_DRAWDOWN:.0%}",
                  "bearish_floor": {"min_episodes": MIN_BEAR_EPISODES, "min_span_years": MIN_BEAR_SPAN_YEARS,
                                    "min_nonoverlap_windows": BEARISH_FLOOR}},
        "forward_windows_sessions": FWD,
        "note": "EXPLORATORY regime tags for History-Analysis retrieval; NOT a signal. Forward returns + MDD "
                "are realized ^GSPC paths (None until the window elapsed). 看空 analogs are episode-floor "
                "fail-closed; raw session counts are telemetry only.",
        "regime_summary": summarize(daily),
        "correction_episodes": eps,
        "regime_runs": regime_runs(daily),
        "daily": daily,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    qual = [e for e in eps if not e.get("ongoing")]
    print(f"[regime-hist] {len(daily)} sessions, {len(eps)} correction episodes "
          f"({len(qual)} closed) → {args.output}")
    for e in eps:
        print(f"  episode {e['episode_id']}: {e['start']}→{e['end']} dd {e['drawdown_pct']}"
              f"{' (ongoing)' if e['ongoing'] else ''}")
    for reg in REGIMES:
        s = payload["regime_summary"][reg]; b = s["fwd_60d"]
        print(f"  {reg:11s}: {s['days']:4d} days | 60d mean {b['mean']} p10 {b['p10']} "
              f"worst_mdd {b['worst_mdd']} (n={b['resolved']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
