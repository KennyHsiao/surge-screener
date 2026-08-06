"""美股 · 機構持倉 — what an investment manager HOLDS (13F via SEC EDGAR).

The inverse of 機構持股 (which is stock → who holds it): pick a fund / 大戶
(Berkshire / ARK / Burry …) → its latest 13F-HR portfolio. 100% free via SEC
EDGAR. 13F is QUARTERLY with a ~45-day filing lag — surfaced prominently so the
user reads the holdings as of the right date. Read-only, not advice.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

import pandas as pd
import streamlit as st

from api.models import UnavailableReason

from . import _components, _read_api, _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_TOP_N = 100  # huge quant books (Citadel ~12k positions) → show the top by value

FundCatalogStatus: TypeAlias = Literal[
    "api_available",
    "api_unavailable",
    "api_failure",
]
FundCatalogReason: TypeAlias = (
    UnavailableReason | _read_api.ClientFailureReason | None
)


@dataclass(frozen=True, slots=True)
class FundCatalogState:
    status: FundCatalogStatus
    options: tuple[_read_api.FundCatalogOption, ...]
    reason: FundCatalogReason


@dataclass(frozen=True, slots=True)
class PortfolioTarget:
    query: str
    label: str
    quick_pick_name: str | None


def _load(name_or_cik: str) -> dict | None:
    # No st.cache_data here: edgar_13f.get_13f already disk-caches SUCCESS for 1d
    # (cache.py) but never caches a None failure — so a transient EDGAR 403/timeout
    # self-heals on the next interaction instead of being pinned for a day. It
    # never raises, but guard anyway so EDGAR hiccups can't crash the page.
    from scripts import edgar_13f

    try:
        return edgar_13f.get_13f(name_or_cik)
    except Exception:  # noqa: BLE001
        return None


def _load_fund_catalog() -> FundCatalogState:
    result = _read_api.load_fund_catalog()
    if isinstance(result, _read_api.FundCatalogApiAvailable):
        return FundCatalogState("api_available", result.options, None)
    if isinstance(result, _read_api.FundCatalogApiUnavailable):
        return FundCatalogState("api_unavailable", (), result.reason)
    return FundCatalogState("api_failure", (), result.reason)


def _unavailable_message(reason: FundCatalogReason) -> str:
    detail = {
        "missing": "找不到投資大戶快選資料。",
        "invalid_json": "投資大戶快選資料尚未完整寫入或 JSON 格式無效。",
        "invalid_shape": "投資大戶快選資料格式不符合預期。",
        "unreadable": "投資大戶快選資料目前無法讀取。",
    }.get(reason, "投資大戶快選資料目前無法讀取。")
    return f"投資大戶快選資料目前無法使用：{detail}仍可輸入 CIK 查詢。"


def _safe_reason(
    reason: FundCatalogReason,
) -> str:
    if reason in (
        _components.ARTIFACT_REASON_CODES
        | _components.CLIENT_FAILURE_REASON_CODES
        | _components.UI_REASON_CODES
    ):
        return str(reason)
    return "read_failure"


def _catalog_data_state(catalog: FundCatalogState) -> _components.DataState:
    content = "populated" if catalog.options else "empty"
    if catalog.status == "api_available":
        return _components.DataState(
            source="authoritative",
            content=content,
            freshness="unknown",
            operation="idle",
            source_id="institutions.funds",
            recovery_key="manual-cik" if content == "empty" else None,
        )
    return _components.DataState(
        source="unavailable",
        content="unknown",
        freshness="unknown",
        operation="idle",
        source_id="institutions.funds",
        reason_code=_safe_reason(catalog.reason),
        recovery_key="manual-cik",
    )


def _resolve_target(
    options: tuple[_read_api.FundCatalogOption, ...],
    pick: str | None,
    cik_in: str,
) -> PortfolioTarget | None:
    manual_cik = cik_in.strip()
    if manual_cik:
        return PortfolioTarget(manual_cik, manual_cik, None)
    if pick is None:
        return None
    for option in options:
        if option.display_name == pick:
            return PortfolioTarget(option.cik, option.display_name, option.display_name)
    return None


def _display_data(data: dict, target: PortfolioTarget) -> dict:
    if target.quick_pick_name is None:
        return data
    fund = data.get("fund")
    if fund and str(fund).strip() != target.query:
        return data
    displayed = dict(data)
    displayed["fund"] = target.quick_pick_name
    return displayed


def _render_holdings(data: dict) -> None:
    holdings = data.get("holdings") or []
    if not holdings:
        st.info("此申報無持股明細(可能為 13F-NT 合併申報,或僅持非 13(f) 證券)。")
        return
    shown = holdings[:_TOP_N]
    st.markdown(f"#### 持倉明細(依市值,前 {len(shown)} / 共 {len(holdings):,} 檔)")
    maxpct = max((h.get("pct") or 0) for h in shown) or 1.0
    disp = pd.DataFrame([{
        "標的": h.get("issuer") or "?",
        "占組合%": h.get("pct"),
        "市值($B)": (h.get("value") or 0) / 1e9,
        "股數": h.get("shares"),
        "選擇權": h.get("put_call") or "",
    } for h in shown])
    st.dataframe(
        disp, hide_index=True, use_container_width=True, height=520,
        column_config={
            "標的": st.column_config.TextColumn(width="large"),
            "占組合%": st.column_config.ProgressColumn(min_value=0, max_value=float(maxpct),
                                                      format="%.2f%%", help="占申報組合市值比重"),
            "市值($B)": st.column_config.NumberColumn(format="$%.2f"),
            "股數": st.column_config.NumberColumn(format="%d"),
            "選擇權": st.column_config.TextColumn(width="small", help="Put/Call;空白=普通股"),
        },
    )
    st.caption("ℹ️ 13F 只列 CUSIP + 公司名、**無股票代號**(代號需自行對應);市值已正規化為美元。"
               "僅含**申報的長部位**(美股 / 選擇權),不含空單、現金、海外或非 13(f) 證券。")


def render(embedded: bool = False) -> None:
    if not embedded:
        st.header("🏦 機構持倉")
    st.caption("某機構 → **它持有哪些股票**:投資大戶的 13F 申報持倉。免費 SEC EDGAR。"
               "與「機構持股」相反(那是『股票→誰持有它』)。唯讀、非投資建議。")

    catalog = _load_fund_catalog()
    state = _catalog_data_state(catalog)
    if catalog.status != "api_available" or state.content == "empty":
        _components.render_state_banner(state)
    else:
        _components.render_source_meta(state)

    options = catalog.options
    names = [option.display_name for option in options]
    option_by_name = {option.display_name: option for option in options}

    def format_option(name: str) -> str:
        option = option_by_name.get(name)
        note = option.note if option is not None else ""
        return f"{name} · {note}".strip(" ·")

    c1, c2 = st.columns([3, 2])
    pick = c1.selectbox("投資大戶快選(可在 content/funds.json 增刪)", names,
                        index=0 if names else None,
                        format_func=format_option)
    cik_in = c2.text_input("或輸入 CIK", placeholder="例如 1067983").strip()

    target = _resolve_target(options, pick, cik_in)
    if not target:
        st.info("選一個投資大戶,或輸入 CIK。")
        return

    with st.spinner(f"抓取 {target.label} 的 13F(SEC EDGAR)…"):
        data = _load(target.query)
    if not data:
        st.warning(f"查無 13F:`{target.label}`(CIK 錯誤、此機構未申報 13F,或暫時無法連線 SEC EDGAR)。"
                   "註:七大巨頭等**營運公司不申報 13F**,沒有基金式持倉組合。可稍後重試。")
        return
    data = _display_data(data, target)

    # ── Prominent lag banner (the user explicitly wants the delay flagged) ──
    lag = data.get("lag_days")
    rd, fd = data.get("report_date"), data.get("filing_date")
    banner = (f"⚠️ **資料截至 {rd}(季底)** · 於 {fd} 申報 · **距今約 {lag} 天**。"
              "13F 為**季度、延遲申報**,反映上一季底的部位,非即時持倉。")
    (st.error if (lag or 0) > 150 else st.warning)(banner)

    cols = st.columns(4)
    _shared.metric_card(cols[0], "機構", data.get("fund", "?"))
    _shared.metric_card(cols[1], "持股檔數", f"{data.get('holdings_count', 0):,}")
    _shared.metric_card(cols[2], "申報總市值", f"${data.get('total_value', 0) / 1e9:,.1f}B")
    _shared.metric_card(cols[3], "資料季底", rd or "?")

    _render_holdings(data)
