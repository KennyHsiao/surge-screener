#!/usr/bin/env python3
"""LLM theme classification for a list of US tickers (e.g. "AI supercycle").

The themes (cross-sector) live in content/themes.json as a name→description
taxonomy the user hand-maintains; membership is decided by the LLM. Sector/
industry (from scripts/sector_free) is fed in as a hint so the model classifies
from verified data rather than guessing. Result is cached 30 days (a watchlist's
theme membership is stable). Provider "auto" resolves to the Codex ChatGPT
subscription backend.

CLI:  python scripts/theme_classify.py NVDA AMD SOFI
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Shared subscription-only Codex client.
try:
    from llm_client import LLMClient
except ImportError:  # imported as scripts.theme_classify
    from scripts.llm_client import LLMClient

_THEMES_FILE = Path(__file__).resolve().parent.parent / "content" / "themes.json"


def _cached(namespace: str, params, ttl: float, compute):
    """Best-effort disk cache; falls back to plain compute() if unavailable."""
    try:
        try:
            from cache import get_or_compute
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "cache", Path(__file__).parent / "cache.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            get_or_compute = mod.get_or_compute
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def load_taxonomy() -> dict[str, str]:
    """{theme_name: description} from content/themes.json (or {} on failure)."""
    try:
        return (json.loads(_THEMES_FILE.read_text(encoding="utf-8")) or {}).get("themes", {}) or {}
    except Exception:
        return {}


def _parse_json(raw: str) -> dict:
    """Extract a JSON object from an LLM reply (tolerate ```json fences / prose)."""
    if not raw:
        return {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def _llm_classify(tickers: list[str], taxonomy: dict[str, str], sectors: dict) -> dict[str, list]:
    theme_lines = "\n".join(f"- {name}: {desc}" for name, desc in taxonomy.items())
    hint_lines = []
    for t in tickers:
        s = (sectors or {}).get(t) or {}
        hint_lines.append(f"  {t}: {s.get('sector') or '?'} / {s.get('industry') or '?'}")
    system = (
        "You are an equity sector/theme analyst. Classify each US stock ticker into "
        "ZERO OR MORE of the THEMES provided. A ticker may match several themes or none. "
        "Use ONLY the exact theme names given — never invent themes. Base it on the company's "
        "actual business and the sector/industry hint. Return ONLY valid JSON: an object mapping "
        "each ticker to an array of matching theme names. No prose, no markdown."
    )
    user = (
        f"THEMES (name: meaning):\n{theme_lines}\n\n"
        f"TICKERS (ticker: sector / industry):\n" + "\n".join(hint_lines) + "\n\n"
        f'Return JSON for EXACTLY these tickers {tickers}, e.g. '
        f'{{"NVDA": ["AI supercycle"], "SOFI": ["金融 / Fintech"]}}.'
    )
    raw = LLMClient(provider="auto").chat(system, user, max_tokens=2000)
    data = _parse_json(raw)
    valid = set(taxonomy)
    out = {}
    for t in tickers:
        got = data.get(t) or data.get(t.upper()) or data.get(t.lower()) or []
        out[t] = [th for th in got if th in valid] if isinstance(got, list) else []
    return out


def classify_themes(tickers, taxonomy: dict | None = None, sectors: dict | None = None) -> dict[str, list]:
    """{TICKER: [theme,...]} via one batched LLM call, cached 30d by (tickers, themes).

    Raises if the LLM is unavailable (e.g. no Codex ChatGPT login) — callers should
    catch and degrade gracefully (themes are an overlay; sector grouping still works).
    """
    tickers = sorted({str(t).upper().strip() for t in tickers if str(t).strip()})
    if not tickers:
        return {}
    taxonomy = taxonomy or load_taxonomy()
    if not taxonomy:
        return {t: [] for t in tickers}
    params = {"tickers": tickers, "themes": sorted(taxonomy)}
    return _cached("theme", params, 2592000,
                   lambda: _llm_classify(tickers, taxonomy, sectors or {}))


if __name__ == "__main__":
    import sys
    syms = sys.argv[1:] or ["NVDA", "AMD", "SOFI", "AVGO"]
    print(json.dumps(classify_themes(syms), indent=2, ensure_ascii=False))
