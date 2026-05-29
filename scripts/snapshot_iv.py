#!/usr/bin/env python3
"""Record today's ATM IV for a watchlist into the IV-history store.

Run daily (e.g. from the GitHub Action, after market close when chain IV is
populated) so reports/iv_history/ accumulates the 52-week base that
scripts/iv_history.py needs for IV Rank/Percentile.

Only REAL chain ATM IV is recorded (sane-bounded); when the feed returns garbage
(near-zero IV / market closed) the ticker is skipped rather than polluting history.

Usage:
    python scripts/snapshot_iv.py NVDA AMD MU            # explicit list
    python scripts/snapshot_iv.py                        # tickers from scored_candidates.json, else a default set
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

from iv_history import record_iv  # noqa: E402
from momentum_options import _atm_iv, _pick_expiry  # noqa: E402

DEFAULT_WATCHLIST = ["NVDA", "AMD", "AVGO", "MU", "SMCI", "TSLA", "MRVL", "PLTR"]


def _watchlist(args: list[str]) -> list[str]:
    if args:
        return [a.upper().lstrip("$") for a in args]
    scored = _ROOT / "scored_candidates.json"
    try:
        if scored.is_file():
            d = json.loads(scored.read_text())
            ts = [c.get("ticker") for c in d.get("all_scored", []) if c.get("ticker")]
            if ts:
                return ts
    except Exception:
        pass
    return DEFAULT_WATCHLIST


def main() -> int:
    import yfinance as yf
    tickers = _watchlist(sys.argv[1:])
    recorded, skipped = 0, 0
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            exps = tk.options
            expiry, _ = _pick_expiry(exps) if exps else (None, None)
            if not expiry:
                skipped += 1
                continue
            calls = tk.option_chain(expiry).calls
            spot = float(tk.fast_info.last_price)
            iv, _est = _atm_iv(calls, spot, fallback=None)  # real IV only
            if iv:
                record_iv(t, iv)
                recorded += 1
                print(f"  {t}: ATM IV {iv:.3f} ({expiry})")
            else:
                skipped += 1
                print(f"  {t}: skipped (no usable chain IV)")
        except Exception as e:
            skipped += 1
            print(f"  {t}: error {type(e).__name__}: {e}")
    print(f"[snapshot_iv] recorded {recorded}, skipped {skipped} of {len(tickers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
