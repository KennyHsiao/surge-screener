"""美股 · IBKR 對帳 — read-only reconciliation of screener picks vs. real IBKR positions.

Reads reports/reconciliation.json (written locally by
`python scripts/ibkr_client.py reconcile`). Strictly read-only: this page never
places, modifies, or cancels any order. IBKR is local-only, so the live "重新對帳"
button is disabled unless ib_async is installed AND a Gateway is reachable.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Per-leg detail columns → zh-TW headers.
_LEG_COLS = ["label", "qty", "avg_cost", "market_price", "return_pct", "unrealized_pnl"]
_LEG_RENAME = {
    "label": "合約", "qty": "口數", "avg_cost": "成本",
    "market_price": "現價", "return_pct": "報酬%", "unrealized_pnl": "未實現$",
}


def _legs_df(legs: list[dict]) -> pd.DataFrame:
    """Per-leg rows → tidy, zh-TW-labelled DataFrame for st.dataframe."""
    df = pd.DataFrame(legs or [])
    for c in _LEG_COLS:                      # tolerate missing keys
        if c not in df.columns:
            df[c] = None
    return df[_LEG_COLS].rename(columns=_LEG_RENAME)


_FLAT_COLS = ["底層", "合約", "口數", "成本", "現價", "報酬%", "未實現$"]


def _flat_legs_df(rows: list[dict]) -> pd.DataFrame:
    """All legs across underlyings → ONE flat table (a 底層 column instead of
    per-underlying expanders), sorted by each underlying's total P&L."""
    ordered = sorted(rows, key=lambda x: x.get("total_unrealized_pnl") or 0,
                     reverse=True)
    out = []
    for r in ordered:
        sym = r.get("ticker", "?")
        for leg in (r.get("legs") or []):
            if not isinstance(leg, dict):
                continue
            out.append({
                "底層": sym, "合約": leg.get("label"), "口數": leg.get("qty"),
                "成本": leg.get("avg_cost"), "現價": leg.get("market_price"),
                "報酬%": leg.get("return_pct"), "未實現$": leg.get("unrealized_pnl"),
            })
    return pd.DataFrame(out, columns=_FLAT_COLS)


def _money(v) -> str:
    return f"${v:+,.0f}" if isinstance(v, (int, float)) else "—"


def _money_md(v) -> str:
    """Money string with Streamlit markdown colour (green +, red −) like TWS."""
    if not isinstance(v, (int, float)):
        return "—"
    s = f"${v:+,.0f}"
    return f":green[{s}]" if v > 0 else (f":red[{s}]" if v < 0 else s)


def _num(spec):
    """Cell formatter that tolerates None/NaN (→ '—')."""
    return lambda v: spec.format(v) if isinstance(v, (int, float)) and v == v else "—"


def _pnl_color(v) -> str:
    if not isinstance(v, (int, float)) or v != v:
        return ""
    return f"color: {_shared.GREEN}" if v > 0 else (f"color: {_shared.RED}" if v < 0 else "")


def _style_pnl(df: pd.DataFrame):
    """Style a leg table like IBKR/TWS: green/red P&L + tidy number formatting.
    Returns a pandas Styler (st.dataframe still sorts on the underlying values)."""
    fmt = {"報酬%": _num("{:+.1f}%"), "未實現$": _num("{:+,.0f}"),
           "成本": _num("{:.2f}"), "現價": _num("{:.2f}"), "口數": _num("{:g}")}
    fmt = {k: v for k, v in fmt.items() if k in df.columns}
    color_cols = [c for c in ("報酬%", "未實現$") if c in df.columns]
    return df.style.map(_pnl_color, subset=color_cols).format(fmt)


def _total_unrealized(rec: dict) -> float:
    """Sum unrealized P&L across every held leg (matched + held-not-tracked)."""
    total = 0.0
    for bucket in ("matched", "held_not_in_ledger"):
        for r in rec.get(bucket, []):
            for leg in r.get("legs", []):
                total += leg.get("unrealized_pnl") or 0
    return total


def _render_matched(rows: list[dict]) -> None:
    st.subheader(f"✅ 在 ledger 且持有 ({len(rows)})")
    if not rows:
        st.caption("沒有同時出現在 screener ledger 又實際持有的底層。")
        return
    for r in rows:
        zone = ""
        if r.get("suggested_entry_low") is not None and r.get("suggested_entry_high") is not None:
            zone = f" · 建議區 {r['suggested_entry_low']}–{r['suggested_entry_high']}"
        fwd = r.get("fwd_30d_return")
        fwd_txt = f" · 當初 30d 預期 {fwd:+.1f}%" if fwd is not None else ""
        st.markdown(f"**{r['ticker']}**  ({r.get('verdict') or '-'}, "
                    f"{r.get('scan_date') or '-'}){zone}{fwd_txt}  ·  "
                    f"合計未實現 {_money_md(r.get('total_unrealized_pnl'))}")
        st.dataframe(_style_pnl(_legs_df(r.get("legs"))),
                     hide_index=True, use_container_width=True)


def _render_ledger_not_held(rows: list[dict]) -> None:
    st.subheader(f"📋 screener 有建議、未持有 ({len(rows)})")
    if not rows:
        st.caption("所有 screener 建議都已建立部位(或沒有建議)。")
        return
    df = pd.DataFrame([{
        "代號": r["ticker"], "判斷": r.get("verdict") or "-",
        "掃描日": r.get("scan_date") or "-",
        "建議低": r.get("suggested_entry_low"),
        "建議高": r.get("suggested_entry_high"),
    } for r in rows])
    st.dataframe(df, hide_index=True, use_container_width=True)


def _render_held_not_tracked(rows: list[dict]) -> None:
    st.subheader(f"🔎 你持有、screener 未追蹤 ({len(rows)})")
    if not rows:
        st.caption("你持有的每個底層 screener 都有追蹤。")
        return
    st.caption("這些是你實際下單、但 screener 沒在 ledger 追蹤的底層 — "
               "代表實單與 screener 已脫節,值得回看。")
    total = sum(r.get("total_unrealized_pnl") or 0 for r in rows)
    n_legs = sum(len(r.get("legs") or []) for r in rows)
    st.markdown(f"{len(rows)} 檔 / {n_legs} 腿 · 合計未實現 {_money_md(total)}")
    st.dataframe(_style_pnl(_flat_legs_df(rows)),
                 hide_index=True, use_container_width=True)


def _render_refresh_button() -> None:
    """Live re-reconcile — local-only, read-only. Synchronous (Streamlit reruns
    the script), so the page is busy for the connect window; connect() bounds that
    to a wall-clock budget (~14s worst case), and reconcile() never raises."""
    from scripts import ibkr_client  # lazy: import never fails (ib_async optional)

    if not ibkr_client.available():
        st.button("↻ 從 IBKR 重新對帳", disabled=True,
                  help="需要本機安裝 ib_async(IBKR 僅限本機)。"
                       "pip install -r requirements-ibkr.txt")
        st.caption("ℹ️ IBKR 為本機限定;雲端/CI 不安裝 ib_async,故此鈕停用。"
                   "請在本機開 Gateway 後使用。")
        return

    if st.button("↻ 從 IBKR 重新對帳", type="primary"):
        with st.spinner("連線 IBKR Gateway 對帳中(唯讀,最多約 10–15 秒)…"):
            try:
                rec = ibkr_client.reconcile()  # readonly=True inside connect()
            except Exception as e:             # defensive: never crash the page
                st.error(f"對帳失敗:{e}")
                return
        if not rec.get("reachable"):
            st.warning("找不到可連線的 IBKR Gateway/TWS。"
                       "請先在本機開啟 Gateway 並啟用 API,再重試。")
            return
        import json
        out = _shared.REPORTS_DIR / "reconciliation.json"
        try:
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        except Exception:
            pass
        _shared.load_reconciliation.clear()
        _shared.load_json.clear()
        st.success("對帳完成,已更新。")
        st.rerun()


def render() -> None:
    st.header("🧾 IBKR 對帳")
    st.caption("screener 預測 vs. 你的真實 IBKR 持倉(按底層分組)。"
               "嚴格唯讀 — 此頁永不下單。IBKR 為本機限定。")

    _render_refresh_button()
    st.markdown("---")

    rec = _shared.load_reconciliation()
    if rec is None:
        st.info("尚無對帳資料。請先在本機開 Gateway 跑:\n\n"
                "```bash\npython scripts/ibkr_client.py reconcile\n```")
        return

    c = st.columns(3)
    c[0].metric("持倉合計未實現 P&L", _money(_total_unrealized(rec)))
    c[1].metric("已對帳底層", len(rec.get("matched", [])))
    c[2].metric("持有但未追蹤", len(rec.get("held_not_in_ledger", [])))
    st.markdown("---")

    _render_matched(rec.get("matched", []))
    st.markdown("---")
    _render_ledger_not_held(rec.get("ledger_not_held", []))
    st.markdown("---")
    _render_held_not_tracked(rec.get("held_not_in_ledger", []))
