#!/usr/bin/env python3
"""Forward validation for unusual options-flow signals.

The options-flow scanner writes dated snapshots under reports/options_flow/.
This validator turns those append-only snapshots into a tier-level
validation_summary.json that the Analytics DuckDB read model can ingest via
signal_outcomes.

Method:
  * read only YYYY-MM-DD.json snapshots; skip latest.json to avoid double count
  * one entry per ticker/date/direction, entered at the underlying close
  * bullish signals score upward moves; bearish signals score downward moves
  * TOUCH hit-rate asks whether any close reached the tier target
  * horizon_return is the direction-adjusted close-to-close return at window end

The result is exploratory until enough resolved entries accumulate. It is a
free-data validation harness, not a trade execution backtest.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parent.parent
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

OUT_DIR = REPO / "reports" / "options_flow"
DATED_JSON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
TIERS = [("+5%/10d", 0.05, 10), ("+10%/20d", 0.10, 20), ("+15%/40d", 0.15, 40)]
MIN_RESOLVED = 100

PriceLoader = Callable[[str, str], pd.Series | pd.DataFrame | None]

import retro_factor_lift as rfl  # noqa: E402 - Wilson interval
import retro_reconstruct as rr  # noqa: E402 - cached OHLCV fetch


def _direction_side(direction: str | None) -> int | None:
    text = str(direction or "").strip().lower()
    if text in {"bullish", "bull", "call", "calls", "long", "up"}:
        return 1
    if text in {"bearish", "bear", "put", "puts", "short", "down"}:
        return -1
    return None


def evaluate_entry(close: np.ndarray, direction: str | None) -> dict[str, dict[str, Any]]:
    """Pure per-tier outcome for one option-flow signal.

    close[0] is the entry close. For bearish signals, horizon_return is
    direction-adjusted: an 8% underlying decline becomes +0.08.
    """
    side = _direction_side(direction)
    base = float(close[0]) if close.size else float("nan")
    out: dict[str, dict[str, Any]] = {}
    for label, pct, win in TIERS:
        seg = np.asarray(close[1:win + 1], dtype=float)
        if side == 1 and np.isfinite(base) and base > 0 and seg.size and np.any(np.isfinite(seg)):
            hit = bool(float(np.nanmax(seg)) >= base * (1.0 + pct))
        elif side == -1 and np.isfinite(base) and base > 0 and seg.size and np.any(np.isfinite(seg)):
            hit = bool(float(np.nanmin(seg)) <= base * (1.0 - pct))
        else:
            hit = False

        resolved = bool(
            side is not None
            and (len(close) - 1) >= win
            and np.isfinite(base)
            and base > 0
            and np.isfinite(close[win])
        )
        raw_return = (float(close[win]) / base - 1.0) if resolved else None
        horizon_return = (raw_return * side) if raw_return is not None and side is not None else None
        out[label] = {
            "resolved": resolved,
            "hit": hit,
            "underlying_return": raw_return,
            "horizon_return": horizon_return,
        }
    return out


def _mean_block(values: list[float]) -> dict[str, Any]:
    n = len(values)
    if n == 0:
        return {"n": 0, "ev": None, "median": None, "win_rate": None}
    arr = np.asarray(values, dtype=float)
    return {
        "n": n,
        "ev": round(float(arr.mean()), 4),
        "median": round(float(np.median(arr)), 4),
        "win_rate": round(float((arr > 0).mean()), 4),
    }


def _aggregate_tier(resolved_rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    rows = [r for r in resolved_rows if r["tiers"][label]["resolved"]]
    n = len(rows)
    hits = sum(1 for r in rows if r["tiers"][label]["hit"])
    lo, hi = rfl._wilson(hits, n) if n else (0.0, 1.0)
    mature = n >= MIN_RESOLVED
    ev = _mean_block([float(r["tiers"][label]["horizon_return"]) for r in rows])
    underlying = _mean_block([float(r["tiers"][label]["underlying_return"]) for r in rows])
    return {
        "resolved": n,
        "hits": hits,
        "hit_rate": round(hits / n, 4) if n else None,
        "wilson90": [round(lo, 4), round(hi, 4)],
        "mature": mature,
        "ev_horizon": ev["ev"] if mature else None,
        "median_horizon": ev["median"] if mature else None,
        "win_rate_horizon": ev["win_rate"] if mature else None,
        "ev_underlying": underlying["ev"] if mature else None,
        "median_underlying": underlying["median"] if mature else None,
    }


def _json_files(flow_dir: Path) -> list[Path]:
    if not flow_dir.is_dir():
        return []
    return sorted(p for p in flow_dir.glob("*.json") if DATED_JSON_RE.match(p.name))


def _collect_entries(flow_dir: str | Path = OUT_DIR) -> list[dict[str, Any]]:
    """Collect append-only option-flow entries, de-duped by ticker/date/direction."""
    src_dir = Path(flow_dir)
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in _json_files(src_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        signals = data.get("signals")
        if not isinstance(signals, list):
            continue
        as_of = str(data.get("as_of") or path.stem)[:10]
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            ticker = str(signal.get("ticker") or "").upper().strip()
            direction = str(signal.get("direction") or "").lower().strip()
            if not ticker or _direction_side(direction) is None:
                continue
            key = (ticker, as_of, direction)
            entry = {
                "ticker": ticker,
                "entry_date": as_of,
                "direction": direction,
                "flow_score": signal.get("flow_score"),
                "source_file": path.name,
            }
            old = seen.get(key)
            old_score = old.get("flow_score") if old else None
            new_score = entry.get("flow_score")
            if old is None or (isinstance(new_score, (int, float))
                               and not isinstance(old_score, (int, float))) \
                    or (isinstance(new_score, (int, float))
                        and isinstance(old_score, (int, float))
                        and float(new_score) > float(old_score)):
                seen[key] = entry
    return list(seen.values())


def _normalize_index(index: pd.Index) -> pd.DatetimeIndex:
    idx = pd.to_datetime(index, errors="coerce")
    if isinstance(idx, pd.DatetimeIndex):
        try:
            idx = idx.tz_localize(None)
        except TypeError:
            idx = idx.tz_convert(None)
        return idx.normalize()
    return pd.DatetimeIndex(idx).normalize()


def _default_price_loader(ticker: str, entry_date: str) -> pd.Series | None:  # noqa: ARG001
    df = rr._hist_auto_adjust_false(ticker, "2y")
    if df is None or df.empty or "Close" not in df.columns:
        return None
    close = df["Close"].copy()
    close.index = _normalize_index(close.index)
    return close.astype(float)


def _as_close_series(value: pd.Series | pd.DataFrame | None) -> pd.Series | None:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        if "Close" not in value.columns:
            return None
        series = value["Close"]
    else:
        series = value
    if series.empty:
        return None
    out = series.copy()
    out.index = _normalize_index(out.index)
    return out.astype(float)


def _resolve(entry: dict[str, Any], price_loader: PriceLoader) -> dict[str, Any] | None:
    ed = pd.to_datetime(entry.get("entry_date"), errors="coerce")
    if pd.isna(ed):
        return None
    ed = ed.normalize()
    try:
        close = _as_close_series(price_loader(entry["ticker"], str(entry["entry_date"])))
    except Exception:
        return None
    if close is None:
        return None
    fwd = close[close.index >= ed]
    if fwd.empty or not np.isfinite(float(fwd.iloc[0])) or float(fwd.iloc[0]) <= 0:
        return None
    return {
        "ticker": entry["ticker"],
        "entry_date": entry["entry_date"],
        "direction": entry["direction"],
        "tiers": evaluate_entry(fwd.to_numpy(dtype=float), entry["direction"]),
    }


def _load_previous(output: Path) -> dict[str, Any] | None:
    try:
        return json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    except Exception:
        return None


def _should_skip_publish(payload: dict[str, Any], previous: dict[str, Any] | None) -> str | None:
    if not previous:
        return None
    old_resolved = previous.get("price_resolvable")
    new_resolved = payload.get("price_resolvable")
    if isinstance(old_resolved, int) and old_resolved >= 10 and isinstance(new_resolved, int):
        if new_resolved < old_resolved * 0.90:
            return f"price_resolvable collapsed {old_resolved} -> {new_resolved}"
    return None


def run(
    *,
    flow_dir: str | Path = OUT_DIR,
    output: str | Path | None = None,
    price_loader: PriceLoader = _default_price_loader,
) -> dict[str, Any]:
    out = Path(output) if output is not None else Path(flow_dir) / "validation_summary.json"
    entries = _collect_entries(flow_dir)
    resolved_rows = [r for r in (_resolve(e, price_loader) for e in entries) if r is not None]
    by_tier = {label: _aggregate_tier(resolved_rows, label) for label, _pct, _win in TIERS}
    min_resolved = min((t["resolved"] for t in by_tier.values()), default=0)
    as_of = max((str(e["entry_date"]) for e in entries), default=datetime.now(timezone.utc).date().isoformat())
    dropped = len(entries) - len(resolved_rows)
    dropped_pct = round(dropped / len(entries), 4) if entries else None
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of,
        "module": "options_flow",
        "entries_accumulated": len(entries),
        "price_resolvable": len(resolved_rows),
        "dropped_count": dropped,
        "dropped_pct": dropped_pct,
        "min_resolved_across_tiers": min_resolved,
        "min_resolved_for_verdict": MIN_RESOLVED,
        "verdict": (
            "PROVISIONAL - sample below threshold, indicative only"
            if min_resolved < MIN_RESOLVED else "MATURE"
        ),
        "verdict_by_tier": {
            label: ("MATURE" if t["resolved"] >= MIN_RESOLVED else "PROVISIONAL")
            for label, t in by_tier.items()
        },
        "direction_semantics": {
            "bullish": "hit when underlying close reaches +target; horizon_return is close/base - 1",
            "bearish": "hit when underlying close reaches -target; horizon_return is -(close/base - 1)",
        },
        "note": "Options-flow validation is exploratory until MIN_RESOLVED is met per tier. "
                "It validates underlying follow-through from free scanner snapshots, not paid "
                "sweep/block/aggressor data.",
        "by_tier": by_tier,
    }
    guard = _should_skip_publish(payload, _load_previous(out))
    if guard:
        print(f"[options-flow-fwd] refusing to overwrite validation_summary: {guard}", file=sys.stderr)
        return payload
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forward validation for options-flow signals")
    parser.add_argument("--flow-dir", default=str(OUT_DIR))
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)
    payload = run(flow_dir=args.flow_dir, output=args.output)
    print(
        f"[options-flow-fwd] {payload['entries_accumulated']} entries, "
        f"{payload['price_resolvable']} price-resolvable, "
        f"{payload['dropped_count']} dropped ({payload['dropped_pct']}) -> {payload['verdict']}"
    )
    for label, tier in payload["by_tier"].items():
        print(
            f"  {label} [{payload['verdict_by_tier'][label]}]: "
            f"touch {tier['hits']}/{tier['resolved']} "
            f"(rate {tier['hit_rate']}, 90% CI {tier['wilson90']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
