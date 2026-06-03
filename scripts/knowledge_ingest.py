#!/usr/bin/env python3
"""Ingest a paper URL into the knowledge vault — fetch abstract → LLM → card.

Pipeline (verified-data-to-AI: the model only summarises text WE fetched, it never
searches or invents):
  1. httpx GET the url → strip HTML to text (the abstract page is HTML, no PDF lib).
  2. LLMClient(provider="auto").chat(system_prompts/09_factor_extraction_prompt.md,
     <existing-factor list + fetched text>) → structured JSON (title/authors/year/
     venue/dimension/horizon/abstract_summary/factor_hypotheses/grounds).
  3. Write knowledge/papers/<slug>.md (frontmatter + [[factor]] links + url +
     fetched_on), so the paper joins the graph: paper -> factor -> dimension.

The whole fetch+extract is disk-cached (cache.py) keyed on the url, so re-ingesting
is instant and never re-hits the LLM. NEVER fabricates: a field the abstract
doesn't state comes back null with a caveat.

CLI:
  python scripts/knowledge_ingest.py https://www.nber.org/papers/w10925
  python scripts/knowledge_ingest.py <url> --id my-slug --force
  python scripts/knowledge_ingest.py --reading-list            # all of content/reading_list.json
  python scripts/knowledge_ingest.py --reading-list --new-only # only ones without a card
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

VAULT = _ROOT / "knowledge"
_PROMPT = _ROOT / "system_prompts" / "09_factor_extraction_prompt.md"
_READING_LIST = _ROOT / "content" / "reading_list.json"
_UA = ("Mozilla/5.0 (compatible; surge-screener-knowledge/1.0; "
       "+research; admin@surge-screener.app)")
_DIM_NAMES = {f"Dim{i}" for i in range(1, 8)}


def _cached(namespace, params, ttl, compute):
    try:
        from cache import get_or_compute
        return get_or_compute(namespace, params, ttl, compute)
    except Exception:
        return compute()


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:80] or "untitled-paper"


def _factor_index() -> dict:
    """Existing factor keys → (dimension, desc), for the LLM's grounds mapping."""
    from retro_reconstruct import FACTOR_DEFS
    from retro_edgar_backfill import EDGAR_FACTOR_DEFS
    return {k: (d, desc) for k, (d, _s, desc) in {**FACTOR_DEFS, **EDGAR_FACTOR_DEFS}.items()}


def _html_to_text(htmltext: str) -> str:
    t = re.sub(r"(?is)<(script|style|noscript|svg|head).*?</\1>", " ", htmltext)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def _fetch_text(url: str) -> str:
    import httpx
    r = httpx.get(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"},
                  timeout=30, follow_redirects=True)
    r.raise_for_status()
    return _html_to_text(r.text)[:9000]   # abstracts are short; cap landing-page noise


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("```"):
                text = "\n".join(lines[1:i])
                break
    brace = text.find("{")
    if brace == -1:
        raise ValueError("no JSON in LLM reply")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace:i + 1])
    raise ValueError("malformed JSON in LLM reply")


def _extract(url: str, model: str | None) -> dict:
    """Fetch + LLM-extract, disk-cached on the url (30d). Returns the parsed dict
    plus the url. Raises on fetch/LLM/parse failure (caller decides)."""
    def _compute():
        from llm_client import LLMClient
        body = _fetch_text(url)
        if len(body) < 120:
            raise ValueError(f"fetched text too short ({len(body)} chars) — page may need JS")
        findex = _factor_index()
        flist = "\n".join(f"- {k} ({d}): {desc}" for k, (d, desc) in findex.items())
        system = _PROMPT.read_text(encoding="utf-8")
        user = (f"既有因子清單(grounds 只能從這裡挑):\n{flist}\n\n"
                f"=== 以下為從 {url} 抓取的網頁文字(只根據這段內容萃取)===\n{body}")
        llm = LLMClient(provider="auto", model=(model or "claude-opus-4-8"))
        data = _extract_json(llm.chat(system=system, user=user, max_tokens=2000))
        data["url"] = url
        return data
    # never cache a failed/empty extraction (should_cache: needs a title or summary)
    return _cached("paper_ingest", {"url": url}, 2592000, _compute)


def _card(data: dict, slug: str) -> str:
    dim = data.get("dimension") or ""
    dim_link = f"[[{dim}]]" if dim in _DIM_NAMES else dim
    grounds = [g for g in (data.get("grounds") or []) if g]
    authors = ", ".join(data.get("authors") or []) or "—"
    fm = "\n".join([
        "---",
        f"id: {slug}",
        "node_type: paper",
        f'title: "{(data.get("title") or "").replace(chr(34), "")}"',
        f"authors: [{', '.join(data.get('authors') or [])}]",
        f"year: {data.get('year') or ''}",
        f'venue: "{data.get("venue") or ""}"',
        f"url: {data.get('url') or ''}",
        f"dimension: {dim}",
        f"horizon: {data.get('horizon') or 'na'}",
        f"fetched_on: {date.today().isoformat()}",
        "---", "",
    ])
    known = set(_factor_index().keys())
    hyp = data.get("factor_hypotheses") or []
    hyp_lines = []
    for h in hyp:
        g = h.get("grounds_factor")
        glink = f" → [[{g}]]" if g and g in known else ""
        hyp_lines.append(f"- **{h.get('name', '?')}** — {h.get('construction') or ''}"
                         f"{(';效果:' + h['reported_effect']) if h.get('reported_effect') else ''}{glink}")
    g_lines = [f"- [[{g}]]" for g in grounds] or ["- (無對應既有因子;可作為新因子候選)"]
    caveat = data.get("caveat")
    body = (
        f"# {data.get('title') or slug} ({data.get('year') or ''})\n\n"
        f"**作者** {authors} · **出處** {data.get('venue') or '—'} ({data.get('year') or ''})\n"
        f"**連結** {data.get('url')}\n"
        f"**對應維度** {dim_link} · **持有視窗** {data.get('horizon') or 'na'}\n"
        f"**取得** {date.today().isoformat()}(摘要由 LLM 從上述 url 抓取的文字萃取,未經人工核對)\n\n"
        f"{data.get('abstract_summary') or '_(摘要未取得)_'}\n\n"
        f"## 因子假說\n" + ("\n".join(hyp_lines) if hyp_lines else "- (摘要未列出明確因子)") + "\n\n"
        f"## 支持的因子\n" + "\n".join(g_lines) + "\n\n"
        f"## 來源\n- {data.get('url')}(fetched {date.today().isoformat()})\n"
        + (f"\n> ⚠️ {caveat}\n" if caveat else "")
    )
    return fm + body


def _ingest_one(url: str, slug: str | None, model: str | None, force: bool) -> str | None:
    try:
        data = _extract(url, model)
    except Exception as e:  # noqa: BLE001 — network/LLM/parse all degrade to a clear skip
        print(f"[ingest] FAIL {url}: {e}")
        return None
    slug = slug or _slug(data.get("title") or url.rstrip("/").split("/")[-1])
    path = VAULT / "papers" / f"{slug}.md"
    if path.exists() and not force:
        print(f"[ingest] exists (use --force): {path.name}")
        return slug
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_card(data, slug), encoding="utf-8")
    print(f"[ingest] wrote papers/{slug}.md · dim={data.get('dimension')} "
          f"horizon={data.get('horizon')} grounds={data.get('grounds') or []}")
    return slug


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", help="paper abstract/landing URL")
    ap.add_argument("--id", help="slug for the card (default: from title)")
    ap.add_argument("--reading-list", action="store_true",
                    help="ingest every paper in content/reading_list.json")
    ap.add_argument("--new-only", action="store_true",
                    help="with --reading-list: skip ids that already have a card")
    ap.add_argument("--model", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.reading_list:
        papers = (json.loads(_READING_LIST.read_text(encoding="utf-8")) or {}).get("papers", [])
        done = 0
        for p in papers:
            slug = p.get("id")
            if args.new_only and (VAULT / "papers" / f"{slug}.md").exists():
                # only skip if it's already an INGESTED card (has fetched_on != seed)
                t = (VAULT / "papers" / f"{slug}.md").read_text(encoding="utf-8")
                if "fetched_on: seed" not in t:
                    continue
            if _ingest_one(p["url"], slug, args.model, force=True):
                done += 1
        print(f"[ingest] reading-list done: {done}/{len(papers)}")
        return 0

    if not args.url:
        ap.error("provide a URL or --reading-list")
    return 0 if _ingest_one(args.url, args.id, args.model, args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())
