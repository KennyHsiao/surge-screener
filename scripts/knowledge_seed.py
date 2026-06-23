#!/usr/bin/env python3
"""Seed the knowledge/ Obsidian vault from the code's factor registry.

Single source of truth: factors come from FACTOR_DEFS (retro_reconstruct.py) +
EDGAR_FACTOR_DEFS (retro_edgar_backfill.py); horizon/sources from
config/factor_meta.json; literature from content/reading_list.json. We emit
markdown cards with YAML frontmatter + [[wikilinks]] (same convention as the
repo's own memory/ vault) so Obsidian renders the graph:

    paper -> factor -> dimension   (and later factor -> archetype -> result)

This SEEDS the network. Two siblings keep it alive without clobbering edits:
  * knowledge_ingest.py  — add a paper card from a URL (fetch abstract -> LLM)
  * knowledge_sync.py    — write validation results (lift/precision/verdict) back

Idempotency: factor/paper cards are CREATE-IF-ABSENT (so ingest/sync edits and
any hand notes survive a re-seed); dimension hubs + MOC.md are always rebuilt
(pure indexes). Pass --force to regenerate everything.

CLI:  python scripts/knowledge_seed.py [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

VAULT = _ROOT / "knowledge"
_FACTOR_META = _ROOT / "config" / "factor_meta.json"
_READING_LIST = _ROOT / "content" / "reading_list.json"

import knowledge_graph as kg

# Dimension display names (zh-TW) — hub titles.
DIM_NAMES = {
    "Dim1": "技術面 (Technical)",
    "Dim2": "催化劑 / 事件 (Catalyst)",
    "Dim3": "情緒 (Sentiment)",
    "Dim4": "機構 / 內部人籌碼 (Institutional)",
    "Dim5": "板塊 / 市場環境 (Sector & Regime)",
    "Dim6": "選擇權流 (Options Flow)",
    "Dim7": "分析師共識 (Analyst)",
}
HORIZON_LABEL = {"short": "short(數日~2週)", "mid": "mid(2週~3月)",
                 "long": "long(3月+)", "na": "na"}


def _factor_defs() -> dict:
    """Merge the code's factor registry (single source of truth)."""
    from retro_reconstruct import FACTOR_DEFS
    from retro_edgar_backfill import EDGAR_FACTOR_DEFS
    merged = {}
    for k, (dim, sub, desc) in {**FACTOR_DEFS, **EDGAR_FACTOR_DEFS}.items():
        merged[k] = {"dimension": dim, "subfactor": sub, "desc": desc}
    return merged


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _yaml_val(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    if v is None or v == "":
        return ""
    s = str(v)
    return f'"{s}"' if (":" in s or s.startswith(("[", "#"))) else s


def _frontmatter(d: dict) -> str:
    lines = ["---"]
    for k, v in d.items():
        lines.append(f"{k}: {_yaml_val(v)}")
    lines.append("---\n")
    return "\n".join(lines)


def _write(path: Path, text: str, *, force: bool, overwrite: bool,
           kg_meta: dict | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force and not overwrite:
        if kg_meta:
            cur = path.read_text(encoding="utf-8")
            new = kg.update_kg_tags_in_text(cur, kg_meta)
            if new != cur:
                path.write_text(new, encoding="utf-8")
                return "tag"
        return "skip"
    if kg_meta:
        text = kg.update_kg_tags_in_text(text, kg_meta)
    path.write_text(text, encoding="utf-8")
    return "write"


# ── card builders ────────────────────────────────────────────────────────────
def _factor_card(key: str, meta: dict, fmeta: dict, papers_by_id: dict) -> str:
    dim, sub, desc = meta["dimension"], meta["subfactor"], meta["desc"]
    fm = fmeta.get(key, {})
    horizon = fm.get("horizon", "na")
    sources = fm.get("sources", []) or []
    fr = _frontmatter({
        "id": key, "node_type": "factor", "dimension": dim, "subfactor": sub,
        "horizon": horizon, "status": "seed",
        "lift": "", "precision": "", "verdict": "", "validated_on": "",
        "sources": sources,
    })
    src_lines = []
    for sid in sources:
        why = (papers_by_id.get(sid) or {}).get("why", "")
        src_lines.append(f"- [[{sid}]]" + (f" — {why}" if why else ""))
    if not src_lines:
        src_lines.append("- (尚無種子文獻 — 用 `python scripts/knowledge_ingest.py <url>` 補上)")
    body = (
        f"# {key} · {desc}\n\n"
        f"**維度** [[{dim}]] · **子因子** {sub} · **持有視窗** {HORIZON_LABEL.get(horizon, horizon)}\n\n"
        f"{desc}\n\n"
        f"## 假說 / 文獻依據\n" + "\n".join(src_lines) + "\n\n"
        f"## 驗證紀錄\n"
        f"_(由 `knowledge_sync.py` 從 factor_lift.json / forward_factor_lift.json 寫回:lift / precision / verdict)_\n\n"
        f"## 相關\n- 維度樞紐:[[{dim}]]\n"
    )
    return fr + body


def _paper_card(p: dict) -> str:
    pid = p["id"]
    fr = _frontmatter({
        "id": pid, "node_type": "paper", "title": p.get("title", ""),
        "authors": p.get("authors", []), "year": p.get("year", ""),
        "venue": p.get("venue", ""), "url": p.get("url", ""),
        "dimension": p.get("dimension", ""), "horizon": p.get("horizon", "na"),
        "fetched_on": "seed",
    })
    authors = ", ".join(p.get("authors", []))
    dim = p.get("dimension", "")
    dim_link = f"[[{dim}]]" if dim in DIM_NAMES else dim
    grounds = p.get("grounds", []) or []
    g_lines = [f"- [[{g}]]" for g in grounds] or ["- (框架/方法論,無單一對應因子)"]
    body = (
        f"# {p.get('title','')} ({p.get('year','')})\n\n"
        f"**作者** {authors} · **出處** {p.get('venue','')} ({p.get('year','')})\n"
        f"**連結** {p.get('url','')}\n"
        f"**對應維度** {dim_link} · **持有視窗** {HORIZON_LABEL.get(p.get('horizon','na'), p.get('horizon'))}\n\n"
        f"{p.get('why','')}\n\n"
        f"## 支持的因子\n" + "\n".join(g_lines) + "\n\n"
        f"> ℹ️ 種子卡:摘要為人工整理。`knowledge_ingest.py` 匯入時會抓取此 url 的 abstract 並記錄 fetched_on。\n"
    )
    return fr + body


def _dimension_hub(dim: str, factors: dict, fmeta: dict, papers: list) -> str:
    fr = _frontmatter({"id": dim, "node_type": "dimension", "dimension": dim})
    fk = [(k, m) for k, m in factors.items() if m["dimension"] == dim]
    f_lines = [
        f"- [[{k}]] — {m['desc']} ({fmeta.get(k, {}).get('horizon', 'na')})"
        for k, m in fk
    ] or ["- (此維度目前無可從價格/EDGAR 重建的因子 — 走 forward 樣本外驗證)"]
    p_lines = [f"- [[{p['id']}]] — {p.get('title','')}"
               for p in papers if p.get("dimension") == dim] or ["- (尚無種子文獻)"]
    body = (
        f"# {dim} — {DIM_NAMES.get(dim, dim)}\n\n"
        f"## 因子\n" + "\n".join(f_lines) + "\n\n"
        f"## 相關文獻\n" + "\n".join(p_lines) + "\n"
    )
    return fr + body


def _moc(factors: dict, fmeta: dict, papers: list) -> str:
    fr = _frontmatter({"id": "MOC", "node_type": "moc", "title": "因子知識網絡 — Map of Content"})
    lines = ["# 因子知識網絡 (MOC)\n",
             "復盤分析的因子↔文獻↔驗證知識網絡。用 Obsidian 開啟此資料夾即可看 graph。\n",
             "## 維度樞紐"]
    for dim in DIM_NAMES:
        lines.append(f"- [[{dim}]] — {DIM_NAMES[dim]}")
    lines.append("\n## 因子(依持有視窗)")
    for hz in ("short", "mid", "long"):
        ks = [k for k in factors if fmeta.get(k, {}).get("horizon") == hz]
        if ks:
            lines.append(f"\n**{HORIZON_LABEL[hz]}**")
            lines += [f"- [[{k}]] — {factors[k]['desc']}" for k in ks]
    lines.append("\n## 文獻")
    for p in papers:
        lines.append(f"- [[{p['id']}]] — {p.get('title','')} ({p.get('year','')})")
    lines.append("\n---\n_由 `scripts/knowledge_seed.py` 產生;`knowledge_ingest.py` 新增文獻、"
                 "`knowledge_sync.py` 回寫驗證結果。_")
    return fr + "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="regenerate ALL cards (overwrites factor/paper cards too)")
    args = ap.parse_args()

    factors = _factor_defs()
    fmeta = _load_json(_FACTOR_META).get("factors", {})
    papers = _load_json(_READING_LIST).get("papers", [])
    papers_by_id = {p["id"]: p for p in papers}

    counts = {"factor": [0, 0], "paper": [0, 0], "dim": 0, "moc": 0, "tags": 0}

    for key, meta in factors.items():
        fm = fmeta.get(key, {})
        kg_meta = {
            "id": key, "node_type": "factor", "dimension": meta["dimension"],
            "subfactor": meta["subfactor"], "horizon": fm.get("horizon", "na"),
            "status": "seed",
        }
        r = _write(VAULT / "factors" / f"{key}.md",
                   _factor_card(key, meta, fmeta, papers_by_id),
                   force=args.force, overwrite=False, kg_meta=kg_meta)
        if r == "tag":
            counts["tags"] += 1
            counts["factor"][1] += 1
        else:
            counts["factor"][0 if r == "write" else 1] += 1

    for p in papers:
        kg_meta = {
            "id": p["id"], "node_type": "paper", "dimension": p.get("dimension", ""),
            "horizon": p.get("horizon", "na"), "status": "seed",
        }
        r = _write(VAULT / "papers" / f"{p['id']}.md", _paper_card(p),
                   force=args.force, overwrite=False, kg_meta=kg_meta)
        if r == "tag":
            counts["tags"] += 1
            counts["paper"][1] += 1
        else:
            counts["paper"][0 if r == "write" else 1] += 1

    for dim in DIM_NAMES:
        _write(VAULT / "dimensions" / f"{dim}.md",
               _dimension_hub(dim, factors, fmeta, papers),
               force=args.force, overwrite=True,
               kg_meta={"id": dim, "node_type": "dimension", "dimension": dim})
        counts["dim"] += 1

    _write(VAULT / "MOC.md", _moc(factors, fmeta, papers),
           force=args.force, overwrite=True,
           kg_meta={"id": "MOC", "node_type": "moc"})
    counts["moc"] = 1

    print(f"vault @ {VAULT}")
    print(f"  factors: {counts['factor'][0]} written / {counts['factor'][1]} kept")
    print(f"  papers:  {counts['paper'][0]} written / {counts['paper'][1]} kept")
    print(f"  dims:    {counts['dim']} (rebuilt) · MOC: {counts['moc']}")
    if counts["tags"]:
        print(f"  tags:    {counts['tags']} existing card(s) refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
