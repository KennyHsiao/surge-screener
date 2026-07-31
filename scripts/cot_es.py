#!/usr/bin/env python3
"""Weekly COT (TFF) + verified ES=F Friday close → analyst report via Codex.

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

# Shared subscription-only Codex client (see llm_client.py).
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
    # "auto" is a compatibility alias for the subscription-only Codex provider.
    return LLMClient(provider="auto", model=model).chat(system_prompt, user, max_tokens=3000)


class PriceUnverified(Exception):
    """ES=F Friday close could not be verified — the anti-hallucination gate."""


def _atomic_write(path: Path, text: str) -> None:
    """Write atomically (temp file + os.replace) so a reader never sees a
    half-written file and a failed write can't corrupt the existing one."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def generate_report(prompt: str = "system_prompts/07_cot_es_analyst_prompt.md",
                    model: str | None = None,
                    output_dir: str = "reports/cot",
                    no_llm: bool = False) -> dict:
    """Fetch verified COT + ES=F data → (optionally) build the report via Codex.

    Reusable by the CLI and the dashboard button. A full run writes the audit
    sidecar ``<friday>.verified.json`` and the report ``<friday>.md`` together,
    atomically, sidecar-before-report — so the pair never drifts out of sync.
    ``no_llm`` is a dry-run: it returns the verified data WITHOUT persisting the
    sidecar (writing it without a matching report would desync an existing one).
    Returns {stamp, verified, md_path, cot_as_of, friday_close}. Raises
    ``PriceUnverified`` if the price can't be verified (never calls the LLM then).
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
    vpath = out_dir / f"{stamp}.verified.json"
    vjson = json.dumps(verified, ensure_ascii=False, indent=2)

    # Dry-run: return the verified data WITHOUT persisting the paired sidecar —
    # writing <stamp>.verified.json with no matching <stamp>.md would desync the
    # audit panel from a previously-generated report.
    if no_llm:
        return {"stamp": stamp, "verified": verified, "md_path": None,
                "cot_as_of": cot["as_of"], "friday_close": prices["friday_close"]}

    # Build the report FIRST: the LLM call can fail, and the sidecar must never
    # get ahead of the .md. On failure nothing is written (the last good pair
    # stays intact). On success write both atomically — sidecar before the .md
    # the UI lists by — so a report only appears once its audit data is on disk.
    report_md = build_report(verified, prompt, model)
    _atomic_write(vpath, vjson)
    md_path = out_dir / f"{stamp}.md"
    _atomic_write(md_path, report_md)
    return {"stamp": stamp, "verified": verified, "md_path": str(md_path),
            "cot_as_of": cot["as_of"], "friday_close": prices["friday_close"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="system_prompts/07_cot_es_analyst_prompt.md")
    ap.add_argument("--model", default=None,
                    help="Optional Codex model; defaults to CODEX_MODEL/account setting")
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
