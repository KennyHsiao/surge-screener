#!/usr/bin/env python3
"""Deterministic TTL file cache (ported from Dexter's src/utils/cache.ts).

Free data fetches (yfinance fundamentals / institutional / options) are slow and
re-run every pipeline pass AND every Streamlit interaction. This caches their
JSON results under reports/.cache/ keyed by a hash of (namespace + params), with
a per-call TTL. Corruption-resilient: a bad/expired entry is deleted and the
value recomputed. Never raises — cache problems must never break a fetch.

Usage:
    from cache import get_or_compute
    data = get_or_compute("fundamentals", {"ticker": "NVDA"}, ttl=21600,
                          compute=lambda: _expensive_fetch("NVDA"))
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

# reports/.cache/ at the repo root (sibling of scripts/). Stable regardless of cwd.
_CACHE_DIR = Path(__file__).resolve().parent.parent / "reports" / ".cache"


def _key(params) -> str:
    blob = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _path(namespace: str, params) -> Path:
    safe_ns = "".join(c if c.isalnum() or c in "-_" else "_" for c in namespace)
    return _CACHE_DIR / safe_ns / f"{_key(params)}.json"


def read_cache(namespace: str, params, ttl: float):
    """Return cached value if present and younger than ttl seconds, else None.

    Deletes corrupt or expired entries on read. Never raises.
    """
    p = _path(namespace, params)
    try:
        if not p.is_file():
            return None
        if ttl is not None and (time.time() - p.stat().st_mtime) > ttl:
            p.unlink(missing_ok=True)
            return None
        entry = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or "data" not in entry:
            p.unlink(missing_ok=True)
            return None
        return entry["data"]
    except Exception:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def write_cache(namespace: str, params, data) -> None:
    """Persist data as JSON. Never raises (cache write must not break a fetch)."""
    p = _path(namespace, params)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        entry = {"namespace": namespace, "params": params, "data": data,
                 "cached_at": time.time()}
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry, default=str), encoding="utf-8")
        os.replace(tmp, p)  # atomic
    except Exception:
        pass


def get_or_compute(namespace: str, params, ttl: float, compute, should_cache=None):
    """Return cached value or compute(), cache, and return it.

    By default a falsy result (None/empty) is NOT cached, so a transient failure
    isn't sticky. Pass ``should_cache(value) -> bool`` to gate caching more
    precisely (e.g. only cache options results where available=True — a
    not-available dict is still truthy). Falls back to plain compute() on error.
    """
    hit = read_cache(namespace, params, ttl)
    if hit is not None:
        return hit
    value = compute()
    cache_it = should_cache(value) if should_cache is not None else bool(value)
    if cache_it:
        write_cache(namespace, params, value)
    return value


if __name__ == "__main__":
    # Tiny self-test.
    import sys
    calls = {"n": 0}

    def _c():
        calls["n"] += 1
        return {"v": 42}

    ns, params = "selftest", {"k": "x"}
    read_cache(ns, params, 0)  # clear any stale
    _path(ns, params).unlink(missing_ok=True)
    a = get_or_compute(ns, params, ttl=60, compute=_c)
    b = get_or_compute(ns, params, ttl=60, compute=_c)
    ok = a == b == {"v": 42} and calls["n"] == 1
    print(f"cache self-test: a={a} b={b} computes={calls['n']} -> {'OK' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
