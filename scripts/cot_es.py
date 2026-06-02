#!/usr/bin/env python3
"""Weekly COT (TFF) + verified ES=F Friday close → analyst report via Claude.

Anti-hallucination by construction: deterministic code fetches verified data
(CFTC official API + yfinance ES=F) and feeds it to the LLM, which only writes
the analysis — never the data retrieval. If the price can't be verified, we
emit the failure message and never call the LLM.

Data sources (both free):
  - COT:   CFTC public reporting API, TFF futures-only resource gpe5-46if
  - Price: yfinance ES=F (continuous front-month, == TradingView ES1!)
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yfinance as yf

# Shared LLM client (claude_agent / anthropic / ...; see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.cot_es)
    from scripts.llm_client import LLMClient

CFTC_TFF_FUTONLY = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
ES_MARKET_NAME = "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE"
PRICE_FAIL_MSG = ("🚨 價格數據取得失敗 (Price Data Unavailable). "
                  "報告暫停生成，請手動確認收盤價後重新執行。")


def _to_int(v) -> int:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def get_cot(market_name: str = ES_MARKET_NAME) -> dict:
    """Latest TFF futures-only record for the exact ES market name."""
    params = {
        "$where": f"market_and_exchange_names = '{market_name}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": 1,
    }
    resp = httpx.get(CFTC_TFF_FUTONLY, params=params, timeout=30.0)
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        raise RuntimeError(f"CFTC: no COT record for '{market_name}'")
    r = rows[0]
    am_l, am_s = _to_int(r.get("asset_mgr_positions_long")), _to_int(r.get("asset_mgr_positions_short"))
    am_dl, am_ds = _to_int(r.get("change_in_asset_mgr_long")), _to_int(r.get("change_in_asset_mgr_short"))
    lm_l, lm_s = _to_int(r.get("lev_money_positions_long")), _to_int(r.get("lev_money_positions_short"))
    lm_dl, lm_ds = _to_int(r.get("change_in_lev_money_long")), _to_int(r.get("change_in_lev_money_short"))
    return {
        "as_of": (r.get("report_date_as_yyyy_mm_dd") or "")[:10],
        "market": r.get("market_and_exchange_names"),
        "open_interest": _to_int(r.get("open_interest_all")),
        "asset_manager": {
            "long": am_l, "short": am_s, "net": am_l - am_s,
            "chg_long": am_dl, "chg_short": am_ds, "chg_net": am_dl - am_ds,
        },
        "leveraged_funds": {
            "long": lm_l, "short": lm_s, "net": lm_l - lm_s,
            "chg_long": lm_dl, "chg_short": lm_ds, "chg_net": lm_dl - lm_ds,
        },
        "source": "CFTC publicreporting.cftc.gov (TFF futures-only, gpe5-46if)",
    }


def get_es_prices(as_of_date: str) -> dict:
    """Verified ES=F close for the COT week's Friday (= as_of Tuesday + 3 days).

    Friday is derived from the COT as-of date, so the 'Tuesday vs Friday' test
    always compares the SAME week — never a current Friday against a stale,
    holiday-delayed COT Tuesday. The exact COT-week Friday close MUST exist in
    the data; if it doesn't (yfinance not yet updated / out of range), we raise
    so the caller trips the price gate instead of publishing stale data.
    """
    hist = yf.Ticker("ES=F").history(period="2mo")
    if hist is None or hist.empty:
        raise RuntimeError("yfinance ES=F returned no data")
    closes = {d.date().isoformat(): float(c) for d, c in hist["Close"].items()}

    as_of = datetime.fromisoformat(as_of_date).date()
    target_friday = as_of + timedelta(days=3)  # Tuesday -> Friday of the COT week

    # STRICT price gate: the COT-week Friday close MUST be present. We do NOT
    # fall back to an earlier weekday — a missing Friday means yfinance is
    # delayed or the session hasn't settled, and publishing e.g. Thursday as
    # "Friday's close" is exactly the stale/mismatched data we must refuse.
    # (Good Friday weeks fail here on purpose; rerun manually once settled.)
    if target_friday.isoformat() not in closes:
        raise RuntimeError(
            f"no verified ES close for COT-week Friday {target_friday.isoformat()} "
            f"(yfinance delayed or not yet settled) — refusing to publish")
    friday_date = target_friday

    fr_idx = next(d for d in hist.index if d.date() == friday_date)
    fr = hist.loc[fr_idx]
    wk = hist[(hist.index.date > as_of) & (hist.index.date <= friday_date)]
    if wk.empty:
        wk = hist[hist.index.date <= friday_date].tail(5)

    age_days = (datetime.now(timezone.utc).date() - as_of).days
    return {
        "symbol": "ES=F (continuous front-month, == TradingView ES1!)",
        "friday_date": friday_date.isoformat(),
        "friday_open": round(float(fr["Open"]), 2),
        "friday_high": round(float(fr["High"]), 2),
        "friday_low": round(float(fr["Low"]), 2),
        "friday_close": round(float(fr["Close"]), 2),
        "week_high": round(float(wk["High"].max()), 2),
        "week_low": round(float(wk["Low"].min()), 2),
        "as_of_date": as_of_date,
        "as_of_close": round(closes[as_of_date], 2) if as_of_date in closes else None,
        "cot_report_age_days": age_days,
        "cot_stale_warning": age_days > 9,  # COT normally ~3-4 days old on release
        "source": "Yahoo Finance via yfinance",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def assemble_verified(cot: dict, prices: dict) -> dict:
    f, t = prices["friday_close"], prices["as_of_close"]
    return {
        "cot": cot,
        "price": prices,
        "tuesday_vs_friday": {
            "as_of_tuesday_close": t,
            "friday_close": f,
            "delta_points": round(f - t, 2) if t is not None else None,
        },
    }


def build_report(verified: dict, prompt_path: str, model: str) -> str:
    system_prompt = Path(prompt_path).read_text(encoding="utf-8")
    user = (
        "以下是已驗證資料(由系統抓取,請勿自行搜尋或臆測):\n```json\n"
        + json.dumps(verified, ensure_ascii=False, indent=2)
        + "\n```\n請依系統提示的格式產出繁體中文週報。"
    )
    # provider "auto": API key in CI, else the logged-in Claude subscription.
    return LLMClient(provider="auto", model=model).chat(system_prompt, user, max_tokens=3000)


class PriceUnverified(Exception):
    """ES=F Friday close could not be verified — the anti-hallucination gate."""


def generate_report(prompt: str = "system_prompts/07_cot_es_analyst_prompt.md",
                    model: str = "claude-opus-4-8",
                    output_dir: str = "reports/cot",
                    no_llm: bool = False) -> dict:
    """Fetch verified COT + ES=F data → (optionally) build the report via Claude.

    Reusable by both the CLI and the dashboard button. Always writes
    ``<friday>.verified.json``; writes ``<friday>.md`` unless ``no_llm``. Returns
    {stamp, verified, md_path, cot_as_of, friday_close}. Raises ``PriceUnverified``
    if the price can't be verified (never calls the LLM in that case).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cot = get_cot()
    try:
        prices = get_es_prices(cot["as_of"])
    except Exception as e:  # price is the anti-hallucination gate
        (out_dir / "_last_error.txt").write_text(
            f"{datetime.now(timezone.utc).isoformat()}\n{PRICE_FAIL_MSG}\n{e}\n",
            encoding="utf-8")
        raise PriceUnverified(str(e)) from e

    verified = assemble_verified(cot, prices)
    stamp = prices["friday_date"]
    # Always persist the verified data (the report's audit trail / UI panel).
    (out_dir / f"{stamp}.verified.json").write_text(
        json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = None
    if not no_llm:
        report_md = build_report(verified, prompt, model)
        md_path = out_dir / f"{stamp}.md"
        md_path.write_text(report_md, encoding="utf-8")

    return {"stamp": stamp, "verified": verified,
            "md_path": str(md_path) if md_path else None,
            "cot_as_of": cot["as_of"], "friday_close": prices["friday_close"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="system_prompts/07_cot_es_analyst_prompt.md")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--output-dir", default="reports/cot")
    ap.add_argument("--no-llm", action="store_true",
                    help="只抓+組裝驗證資料,不呼叫 LLM(測試用)")
    args = ap.parse_args()

    try:
        res = generate_report(args.prompt, args.model, args.output_dir, args.no_llm)
    except PriceUnverified as e:
        print(f"[cot_es] PRICE FETCH FAILED: {e}")
        print(PRICE_FAIL_MSG)
        raise SystemExit(2)

    if args.no_llm:
        print(json.dumps(res["verified"], ensure_ascii=False, indent=2))
        return
    print(f"[cot_es] wrote {res['md_path']} "
          f"(COT as-of {res['cot_as_of']}, ES Fri {res['friday_close']})")


if __name__ == "__main__":
    main()
