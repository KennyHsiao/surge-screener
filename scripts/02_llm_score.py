#!/usr/bin/env python3
"""
Stage 2 — LLM Scoring (Layer 0 + Layer 1)
Layer 0: Base Prompter — compute regime context once.
Layer 1: Breadth Pass — score each candidate on 7 dimensions via LLM.
Outputs scored_candidates.json with regime_context attached.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

# Shared subscription-only Codex client (see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.02_llm_score)
    from scripts.llm_client import LLMClient

try:
    from run_status import RunStatus
except ImportError:  # when imported as a package
    from scripts.run_status import RunStatus

try:
    from scoring_contract import (
        SCORE_LIMITS,
        expected_evidence_score_contract,
        expected_composite_contract,
        expected_technical_contract,
        expected_verdict_contract,
        is_finite_number,
    )
    from promotion_reachability import (
        TECHNICAL_INPUTS,
        UNSUPPORTED_TECHNICAL_PATTERNS,
        safe_build_candidate_diagnostic,
        safe_build_layer1_capabilities,
        safe_summarize_run,
    )
except ImportError:  # when imported as a package
    from scripts.scoring_contract import (
        SCORE_LIMITS,
        expected_evidence_score_contract,
        expected_composite_contract,
        expected_technical_contract,
        expected_verdict_contract,
        is_finite_number,
    )
    from scripts.promotion_reachability import (
        TECHNICAL_INPUTS,
        UNSUPPORTED_TECHNICAL_PATTERNS,
        safe_build_candidate_diagnostic,
        safe_build_layer1_capabilities,
        safe_summarize_run,
    )


TECHNICAL_EVIDENCE_SCHEMA = "technical_evidence_v1"
TECHNICAL_EVIDENCE_UNSUPPORTED_PATTERNS = UNSUPPORTED_TECHNICAL_PATTERNS
TECHNICAL_EVIDENCE_REQUIRED_INPUTS = TECHNICAL_INPUTS


def validate_technical_evidence(evidence: object) -> tuple[bool, list[str]]:
    """Validate the producer-owned technical evidence contract."""
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return False, ["technical evidence must be an object"]
    if evidence.get("schema_version") != TECHNICAL_EVIDENCE_SCHEMA:
        errors.append(f"schema_version must be {TECHNICAL_EVIDENCE_SCHEMA}")
    source = evidence.get("source")
    if not isinstance(source, dict) or source.get("provider") != "yfinance":
        errors.append("source.provider must be yfinance")
    if not isinstance(source, dict) or source.get("dataset") != "daily_ohlcv":
        errors.append("source.dataset must be daily_ohlcv")
    if not isinstance(source, dict) or source.get("price_adjustment") != "auto_adjusted":
        errors.append("source.price_adjustment must be auto_adjusted")
    if not isinstance(source, dict) or source.get("requested_period") != "1y":
        errors.append("source.requested_period must be 1y")
    as_of_date = evidence.get("as_of_date")
    if not isinstance(as_of_date, str) or not as_of_date:
        errors.append("as_of_date is required")
    else:
        try:
            date.fromisoformat(as_of_date)
        except ValueError:
            errors.append("as_of_date must be an ISO calendar date")
    sessions = evidence.get("history_sessions")
    if not isinstance(sessions, int) or isinstance(sessions, bool) or sessions <= 0:
        errors.append("history_sessions must be a positive integer")

    inputs = evidence.get("inputs")
    if not isinstance(inputs, dict):
        return False, [*errors, "inputs must be an object"]
    for key in TECHNICAL_EVIDENCE_REQUIRED_INPUTS:
        item = inputs.get(key)
        if not isinstance(item, dict):
            errors.append(f"inputs.{key} is required")
            continue
        status = item.get("status")
        if status == "available":
            value = item.get("value")
            if value is None:
                errors.append(f"inputs.{key}.value is required when available")
            elif not isinstance(value, (int, float, bool)):
                errors.append(f"inputs.{key}.value must be numeric or boolean")
            elif isinstance(value, (int, float)) and not isinstance(value, bool) and not (
                float("-inf") < float(value) < float("inf")
            ):
                errors.append(f"inputs.{key}.value must be finite")
        elif status == "missing":
            reason = item.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"inputs.{key}.reason is required when missing")
        else:
            errors.append(f"inputs.{key}.status must be available or missing")
    return not errors, errors


def _technical_value(evidence: dict, key: str):
    item = evidence["inputs"][key]
    return item.get("value") if item.get("status") == "available" else None


def compute_grounded_technical_score(evidence: dict) -> tuple[float, dict]:
    """Apply the existing 10/8/9/3 rubric only to producer-owned evidence."""
    ok, errors = validate_technical_evidence(evidence)
    if not ok:
        raise ValueError("invalid technical evidence: " + "; ".join(errors))

    value = lambda key: _technical_value(evidence, key)
    price = value("price")
    ma50 = value("ma50")
    ma150 = value("ma150")
    ma200 = value("ma200")
    ma200_prior = value("ma200_1m_ago")
    low_52w = value("low_52w")
    high_52w = value("high_52w")
    rs_rating = value("rs_rating")

    def all_numeric(*items) -> bool:
        return all(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in items
        )

    trend_conditions = (
        all_numeric(price, ma150, ma200) and price > ma150 and price > ma200,
        all_numeric(ma150, ma200) and ma150 > ma200,
        all_numeric(ma200, ma200_prior) and ma200 > ma200_prior,
        all_numeric(ma50, ma150, ma200) and ma50 > ma150 > ma200,
        all_numeric(price, ma50) and price > ma50,
        all_numeric(price, low_52w) and low_52w > 0 and price >= low_52w * 1.30,
        all_numeric(price, high_52w) and high_52w > 0 and price >= high_52w * 0.75,
        all_numeric(rs_rating) and rs_rating >= 70,
    )
    trend_score = round(sum(bool(condition) for condition in trend_conditions) * 1.25, 2)

    volume_ratio = value("volume_ratio_20d")
    close_position = value("close_position")
    price_change = value("price_change_1d")
    volume_score = 0
    if all_numeric(volume_ratio, close_position) and volume_ratio >= 2 and close_position >= 2 / 3:
        volume_score = 8
    elif all_numeric(volume_ratio, price_change) and volume_ratio >= 1.5 and price_change > 0:
        volume_score = 6
    elif all_numeric(volume_ratio) and volume_ratio >= 1.2:
        volume_score = 3

    pattern_score = 0
    pattern_type = "無可驗證型態"
    for key, points, label in (
        ("vcp", 9, "VCP 續勢"),
        ("cup_with_handle", 8, "杯柄突破"),
        ("flat_base", 7, "平底突破"),
        ("bull_flag", 6, "多頭旗形突破"),
        ("higher_highs_lows_4w", 4, "四週高低點墊高"),
    ):
        if value(key) is True:
            pattern_score, pattern_type = points, label
            break
    if (
        value("w_bottom_shape") is True
        and value("weekly_rsi_bullish_divergence") is True
        and value("w_bottom_neckline_breakout") is True
        and value("daily_macd_zero_cross_10d") is True
        and pattern_score < 7
    ):
        pattern_score, pattern_type = 7, "W 底反轉確認"
    if value("inverse_head_shoulders") is True and pattern_score < 6:
        pattern_score, pattern_type = 6, "反向頭肩突破"

    daily_macd = value("daily_macd")
    fresh_cross = value("daily_macd_golden_cross_10d") is True
    weekly_hist = value("weekly_macd_histogram")
    weekly_hist_previous = value("weekly_macd_histogram_previous")
    macd_score = 0
    macd_state = "缺少可驗證動能確認"
    if (
        fresh_cross
        and all_numeric(weekly_hist, weekly_hist_previous)
        and weekly_hist > 0
        and weekly_hist > weekly_hist_previous
    ):
        macd_score, macd_state = 3, "日線金叉且週線柱體為正並上升"
    elif fresh_cross and all_numeric(daily_macd) and daily_macd >= 0:
        macd_score, macd_state = 2, "日線近期金叉且位於零軸以上"
    elif not fresh_cross and all_numeric(daily_macd) and daily_macd >= 0:
        macd_score, macd_state = 1, "日線位於零軸以上但無近期金叉"

    breakdown = {
        "trend_template": trend_score,
        "volume": volume_score,
        "pattern": pattern_score,
        "pattern_type": pattern_type,
        "macd_confirmation": macd_score,
        "macd_state": macd_state,
    }
    raw_total, applied_cap, total, _ = expected_technical_contract(breakdown)
    breakdown["raw_total"] = raw_total
    breakdown["applied_cap"] = applied_cap
    return total, breakdown


def _technical_missing_tokens(evidence: dict) -> list[str]:
    inputs = evidence.get("inputs") if isinstance(evidence, dict) else {}
    return [
        f"technical:{key}"
        for key in TECHNICAL_EVIDENCE_REQUIRED_INPUTS
        if isinstance(inputs.get(key), dict) and inputs[key].get("status") == "missing"
    ]


# ---------------------------------------------------------------------------
# Data enrichment helpers
# ---------------------------------------------------------------------------

def enrich_with_market_data(tickers: list[dict]) -> dict:
    """Fetch SPY and VIX data for regime context.

    Deliberately UNCACHED / fresh: this is the daily EOD pipeline's market regime,
    consumed once per run, and it has no in-process dedup partner (in CI the
    surge_scan job is the only regime fetcher in its process). Routing it through
    the shared cached_closes (30-min TTL) would trade freshness for a dedup that
    never materialises here — so the regime stays fresh by design. The shared
    cache is for staleness-tolerant UI/local callers (see scripts/_yfinance.py).
    """
    import yfinance as yf

    regime = {}
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if not spy_hist.empty:
            spy_close = spy_hist["Close"].values
            regime["spy_price"] = float(spy_close[-1])
            regime["spy_50dma"] = float(spy_close[-50:].mean()) if len(spy_close) >= 50 else None
            regime["spy_200dma"] = float(spy_close[-200:].mean()) if len(spy_close) >= 200 else None
            # guard None (short history): float > None raises TypeError, which the
            # outer except would swallow — silently dropping the whole regime block
            regime["spy_vs_50dma"] = ("above" if regime["spy_50dma"] is not None
                                      and spy_close[-1] > regime["spy_50dma"] else "below")
            regime["spy_vs_200dma"] = ("above" if regime["spy_200dma"] is not None
                                       and spy_close[-1] > regime["spy_200dma"] else "below")
    except Exception as e:
        print(f"[llm_score] SPY data error: {e}", file=sys.stderr)

    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="5d")
        if not vix_hist.empty:
            regime["vix_level"] = float(vix_hist["Close"].values[-1])
    except Exception as e:
        print(f"[llm_score] VIX data error: {e}", file=sys.stderr)

    return regime


def fetch_options_flow_summary(ticker: str) -> dict | None:
    """Fetch options flow data. Tries Unusual Whales first, falls back to free yfinance."""
    # Try Unusual Whales (paid, full data)
    api_key = os.environ.get("UNUSUAL_WHALES_API_KEY")
    if api_key:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        base = "https://api.unusualwhales.com/api"
        try:
            resp = httpx.get(f"{base}/stock/{ticker}/options-flow",
                             headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return {"source": "unusual_whales",
                        "flow_data": data.get("data", [])[:20]}
        except Exception:
            pass

    # Fallback: free yfinance options chain analysis
    try:
        from scripts.options_free import analyze_options
        result = analyze_options(ticker)
        if result.get("available"):
            return {"source": "yfinance_free", "options_analysis": result}
    except ImportError:
        # Try relative import for when run from project root
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "options_free",
                Path(__file__).parent / "options_free.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result = mod.analyze_options(ticker)
            if result.get("available"):
                return {"source": "yfinance_free", "options_analysis": result}
        except Exception:
            pass

    return None


def fetch_polygon_news(ticker: str) -> list[dict]:
    """Fetch recent news from Polygon API."""
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        return []

    try:
        resp = httpx.get(
            "https://api.polygon.io/v2/reference/news",
            params={"ticker": ticker, "limit": 5, "apiKey": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


def fetch_free_sentiment(ticker: str) -> dict | None:
    """Free social sentiment (StockTwits + Reddit/ApeWisdom). No API key needed.

    Never raises — returns None on any failure so a flaky free source cannot abort
    the whole scoring run (matches fetch_polygon_news / fetch_options_flow_summary).
    """
    try:
        try:
            from scripts.sentiment_free import gather_free_sentiment
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "sentiment_free", Path(__file__).parent / "sentiment_free.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            gather_free_sentiment = mod.gather_free_sentiment
        return gather_free_sentiment(ticker)
    except Exception:
        return None


def _load_free_module(mod_name: str, func_name: str):
    """Import a scripts/<mod_name>.py free-data helper, with a path fallback for
    when 02_llm_score is run as a loose script rather than a package."""
    try:
        mod = __import__(f"scripts.{mod_name}", fromlist=[func_name])
        return getattr(mod, func_name)
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            mod_name, Path(__file__).parent / f"{mod_name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, func_name)


def fetch_fundamentals(ticker: str) -> dict | None:
    """Free fundamentals / key ratios (yfinance). Never raises."""
    try:
        return _load_free_module("fundamentals_free", "gather_fundamentals")(ticker)
    except Exception:
        return None


def fetch_institutional(ticker: str) -> dict | None:
    """Free institutional ownership + insider activity (Dim 4). Never raises."""
    try:
        return _load_free_module("institutional_free", "gather_institutional")(ticker)
    except Exception:
        return None


def fetch_analyst_views(ticker: str) -> dict | None:
    """Free sell-side analyst consensus (Dim 7 / 分析師共識). Never raises."""
    try:
        return _load_free_module("analyst_free", "gather_analyst_views")(ticker)
    except Exception:
        return None


_SECTOR_ROTATION_MEMO: dict = {}


def fetch_sector_rotation() -> dict | None:
    """Verified sector RRG summary for Dimension 5. Never raises.

    Memoized process-wide: the sector snapshot is a single point-in-time read for
    the whole run (like regime_context), so compute_regime_context and every
    per-candidate score_candidate call share ONE computation."""
    if "v" not in _SECTOR_ROTATION_MEMO:
        try:
            _SECTOR_ROTATION_MEMO["v"] = _load_free_module("sector_flow", "rotation_summary")()
        except Exception:
            _SECTOR_ROTATION_MEMO["v"] = None
    return _SECTOR_ROTATION_MEMO["v"]


def gics_to_etf(gics_sector: str | None) -> str | None:
    """Map a candidate's GICS sector string → its SPDR sector ETF. Never raises."""
    try:
        return _load_free_module("sector_flow", "etf_for_gics")(gics_sector)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Layer 0: Regime Context
# ---------------------------------------------------------------------------

def compute_regime_context(llm: LLMClient, screener_prompt: str,
                           market_data: dict) -> dict:
    """Run Layer 0 Base Prompter to compute regime context."""
    from datetime import datetime

    vix = market_data.get("vix_level", 20)
    spy_vs_50 = market_data.get("spy_vs_50dma", "unknown")
    spy_vs_200 = market_data.get("spy_vs_200dma", "unknown")

    # Compute multiplier deterministically per the rules
    multiplier = 1.0
    if spy_vs_200 == "above" and spy_vs_50 == "below" and 20 <= vix <= 25:
        multiplier = 0.85
    elif spy_vs_200 == "below" and 25 <= vix <= 30:
        multiplier = 0.70
    elif spy_vs_200 == "below" and vix > 30:
        multiplier = 0.50

    # Determine VIX regime
    if vix < 15:
        vix_regime = "low"
    elif vix <= 20:
        vix_regime = "normal"
    elif vix <= 30:
        vix_regime = "elevated"
    else:
        vix_regime = "panic"

    # Use LLM to identify active themes
    user_msg = f"""Based on current market conditions:
- SPY vs 50DMA: {spy_vs_50}
- SPY vs 200DMA: {spy_vs_200}
- VIX: {vix}
- Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Identify 3-5 currently active investment themes in the US stock market.
Return ONLY a JSON object with this structure:
{{
  "active_themes": ["theme1", "theme2", ...],
  "regime_warnings": ["warning1", ...],
  "earnings_season_phase": "pre | active | post"
}}"""

    try:
        resp = llm.chat(
            system="You are a market analyst. Return ONLY valid JSON.",
            user=user_msg,
            max_tokens=1024,
        )
        # Extract JSON from response
        themes_data = _extract_json(resp)
    except Exception as e:
        print(f"[llm_score] Theme detection error: {e}", file=sys.stderr)
        themes_data = {"active_themes": [], "regime_warnings": [],
                       "earnings_season_phase": "unknown"}

    regime_context = {
        "scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "spy_vs_50dma": spy_vs_50,
        "spy_vs_200dma": spy_vs_200,
        "vix_level": vix,
        "vix_regime": vix_regime,
        "global_score_multiplier": multiplier,
        "active_themes": themes_data.get("active_themes", []),
        "regime_warnings": themes_data.get("regime_warnings", []),
        "earnings_season_phase": themes_data.get("earnings_season_phase", "unknown"),
    }

    # Verified sector rotation (RRG): store only the LIGHT board-level context in
    # regime_context (small + ASCII) so every downstream prompt that dumps
    # regime_context stays lean. Layer-1 score_candidate pulls the full per-sector
    # by_etf itself (memoized) to ground Dimension 5 — no need to persist/forward the
    # heavy CJK board into the engine-controller / DD / report prompts that ignore it.
    _srot = fetch_sector_rotation()
    regime_context["sector_rotation"] = (
        {"as_of": _srot.get("as_of"), "leaders": _srot.get("leaders"),
         "improving": _srot.get("improving")} if _srot else None)

    return regime_context


# ---------------------------------------------------------------------------
# Layer 1: Breadth Pass
# ---------------------------------------------------------------------------

FAST_SCORING_SYSTEM_PROMPT = """You are a fast first-pass US equity swing screener.
Use only the supplied verified hard-filter fields and regime context.
Do not infer unavailable news, options flow, sentiment, institutional, or analyst data.
Write all human-readable fields in Traditional Chinese, especially key_signals,
key_risks, suggested_entry_zone, suggested_stop, and technical_breakdown values.
嚴格使用繁體中文撰寫所有給交易者閱讀的文字；不要輸出英文句子。
Ticker、欄位名稱、數字、MACD/RSI/VIX/MA/IV 等市場縮寫可以保留英文。
Return ONLY valid JSON matching the requested schema."""


def _compact_regime_context(regime_context: dict) -> dict:
    keys = (
        "scan_date",
        "spy_vs_50dma",
        "spy_vs_200dma",
        "vix_level",
        "vix_regime",
        "global_score_multiplier",
        "active_themes",
        "regime_warnings",
        "earnings_season_phase",
        "sector_rotation",
    )
    return {k: regime_context.get(k) for k in keys if regime_context.get(k) is not None}


def build_fast_score_messages(candidate: dict, regime_context: dict) -> tuple[str, str]:
    """Build a compact prompt for local subscription scoring.

    This mode is deliberately hard-filter-only: it avoids every per-ticker enrichment
    fetch and asks for a rough first-pass ranking that can later be upgraded by full
    Layer-2 due diligence.
    """
    ticker = candidate["ticker"]
    compact_candidate = {
        k: candidate.get(k)
        for k in (
            "ticker",
            "last_price",
            "ma50",
            "ma200",
            "ret_5d",
            "ret_20d",
            "avg_dollar_vol_20d",
            "market_cap",
            "macd_current",
            "macd_zero_cross_10d",
            "macd_golden_cross_10d",
            "rsi_bullish_divergence",
            "has_reversal_pattern",
        )
        if candidate.get(k) is not None
    }
    user = f"""Fast-score this candidate for a local first pass.

Regime:
{json.dumps(_compact_regime_context(regime_context), separators=(',', ':'), default=str)}

Hard-filter candidate data:
{json.dumps(compact_candidate, separators=(',', ':'), default=str)}

Scoring guidance:
- Technical can use trend, momentum, dollar volume, MACD, RSI divergence, and reversal flags.
- Catalyst/sentiment/institutional/options/analyst data are unavailable in fast mode; score those conservatively.
- Use regime.global_score_multiplier after composite_score.
- Mark unavailable dimensions in data_missing.
- Promote only clear technical/regime candidates to WATCHLIST or NEEDS_LAYER_2.
- Write key_signals, key_risks, suggested_entry_zone, suggested_stop, and any
  explanatory strings in Traditional Chinese.
- 嚴格使用繁體中文；不要輸出英文句子。Ticker、欄位名稱、數字與 MACD/RSI/VIX/MA/IV
  等市場縮寫可以保留英文。

Return ONLY JSON:
{{
  "ticker": "{ticker}",
  "as_of_date": "{regime_context.get('scan_date', '')}",
  "verdict": "REJECT | WATCHLIST | NEEDS_LAYER_2",
  "composite_score": <int 0-100>,
  "regime_adjusted_score": <float>,
  "scores": {{
    "technical": <int 0-30>,
    "catalyst": <int 0-16>,
    "sentiment": <int 0-13>,
    "institutional": <int 0-10>,
    "sector_market": <int 0-3>,
    "options_flow": <int 0-20>,
    "analyst": <int 0-8>
  }},
  "technical_breakdown": {{}},
  "key_signals": ["<string>", ...],
  "key_risks": ["<string>", ...],
  "suggested_entry_zone": "<string>",
  "suggested_stop": "<string>",
  "suggested_size_pct": <float>,
  "similar_to_case": null,
  "anti_example_warning": null,
  "novel_pattern": <bool>,
  "risk_vetoes": [],
  "data_missing": ["options_flow", "sentiment", "institutional", "analyst"],
  "due_diligence_required": <bool>
}}"""
    return FAST_SCORING_SYSTEM_PROMPT, user


def _finalize_candidate_result(result: dict, regime_context: dict, *,
                               options_available: bool,
                               sentiment_available: bool,
                               institutional_available: bool,
                               analyst_available: bool,
                               scoring_mode: str,
                               technical_evidence: dict | None = None,
                               evidence_capabilities: dict | None = None) -> dict:
    """Normalize LLM JSON into the pipeline contract."""
    llm_verdict = result.get("verdict")
    llm_composite_score = result.get("composite_score")
    llm_risk_vetoes = result.get("risk_vetoes", [])
    adjustments: list[dict] = []
    dm = result.get("data_missing")
    dm = list(dm) if isinstance(dm, list) else []
    for tok, present in (("options_flow", options_available),
                         ("sentiment", sentiment_available),
                         ("institutional", institutional_available),
                         ("analyst", analyst_available)):
        if not present and tok not in dm:
            dm.append(tok)
    if technical_evidence is not None:
        ok, errors = validate_technical_evidence(technical_evidence)
        if not ok:
            raise ValueError("invalid technical evidence: " + "; ".join(errors))
        scores = result.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(SCORE_LIMITS):
            raise ValueError("scores must contain exactly the seven scoring dimensions")
        for key, limit in SCORE_LIMITS.items():
            score = scores[key]
            if not is_finite_number(score) or not 0 <= score <= limit:
                raise ValueError(f"scores.{key} must be numeric within 0..{limit}")
        if llm_verdict not in {"REJECT", "WATCHLIST", "NEEDS_LAYER_2"}:
            raise ValueError("verdict must be REJECT, WATCHLIST, or NEEDS_LAYER_2")
        if not is_finite_number(llm_composite_score) or not 0 <= llm_composite_score <= 100:
            raise ValueError("composite_score must be numeric within 0..100")
        result["llm_verdict"] = llm_verdict
        result["llm_composite_score"] = llm_composite_score
        result["llm_risk_vetoes"] = llm_risk_vetoes
        result["llm_scores"] = dict(scores)
        grounded_score, grounded_breakdown = compute_grounded_technical_score(
            technical_evidence
        )
        scores["technical"] = grounded_score
        result["technical_breakdown"] = grounded_breakdown
        result["technical_score_method"] = "technical_evidence_v1_rubric_v1"
        _, _, _, technical_adjustments = expected_technical_contract(
            grounded_breakdown
        )
        adjustments.extend(technical_adjustments)
        if evidence_capabilities is not None:
            scores, evidence_adjustments = expected_evidence_score_contract(
                scores, evidence_capabilities
            )
            result["scores"] = scores
            adjustments.extend(evidence_adjustments)
        uncapped_composite, composite, composite_adjustments = (
            expected_composite_contract(scores)
        )
        adjustments.extend(composite_adjustments)
        result["uncapped_composite_score"] = uncapped_composite
        result["composite_score"] = composite
        for token in _technical_missing_tokens(technical_evidence):
            if token not in dm:
                dm.append(token)
        result["technical_evidence"] = technical_evidence
    result["data_missing"] = dm

    composite = result.get("composite_score", 0)
    if not is_finite_number(composite):
        raise ValueError("composite_score must be a finite number")
    multiplier = regime_context.get("global_score_multiplier", 1.0)
    if not is_finite_number(multiplier) or multiplier <= 0:
        raise ValueError("global_score_multiplier must be a positive finite number")
    result["regime_adjusted_score"] = round(composite * multiplier, 1)
    verdict, verdict_adjustments = expected_verdict_contract(
        composite,
        multiplier,
        dm,
        llm_verdict=llm_verdict,
        llm_composite_score=llm_composite_score,
        llm_risk_vetoes=llm_risk_vetoes,
        scoring_mode=scoring_mode,
    )
    adjustments.extend(verdict_adjustments)

    result["verdict"] = verdict
    result["due_diligence_required"] = verdict == "NEEDS_LAYER_2"
    result["score_adjustments"] = adjustments
    result["scoring_mode"] = scoring_mode
    if evidence_capabilities is not None:
        result["evidence_capabilities"] = evidence_capabilities
        result["promotion_reachability"] = safe_build_candidate_diagnostic(
            result,
            evidence_capabilities,
            multiplier,
        )
    return result


def score_candidate_fast(llm: LLMClient, regime_context: dict, candidate: dict) -> dict:
    """Fast local scorer: no enrichment fetches, compact prompt, same output schema."""
    ticker = candidate["ticker"]
    system, user_msg = build_fast_score_messages(candidate, regime_context)
    try:
        resp = llm.chat(system=system, user=user_msg, max_tokens=1536,
                        cache_system=False)
        result = _extract_json(resp)
        result.setdefault("ticker", ticker)
        return _finalize_candidate_result(
            result,
            regime_context,
            options_available=False,
            sentiment_available=False,
            institutional_available=False,
            analyst_available=False,
            scoring_mode="fast",
            technical_evidence=(
                candidate.get("technical_evidence")
                if isinstance(candidate.get("technical_evidence"), dict) else None
            ),
        )
    except Exception as e:
        print(f"[llm_score] Error scoring {ticker}: {e}", file=sys.stderr)
        return {
            "ticker": ticker,
            "verdict": "REJECT",
            "composite_score": 0,
            "regime_adjusted_score": 0,
            "scoring_mode": "fast",
            "error": str(e),
        }


def score_candidate(llm: LLMClient, screener_prompt: str, regime_context: dict,
                    candidate: dict, case_library: str = "",
                    scoring_mode: str = "full") -> dict:
    """Score a single candidate on 7 dimensions via LLM."""
    if scoring_mode == "fast":
        return score_candidate_fast(llm, regime_context, candidate)
    if scoring_mode != "full":
        raise ValueError(f"unknown scoring_mode: {scoring_mode}")
    ticker = candidate["ticker"]
    technical_evidence = candidate.get("technical_evidence")
    evidence_ok, evidence_errors = validate_technical_evidence(technical_evidence)
    if not evidence_ok:
        raise ValueError(
            f"invalid technical evidence for {ticker}: " + "; ".join(evidence_errors)
        )

    # Gather additional data
    news = fetch_polygon_news(ticker)
    options_flow = fetch_options_flow_summary(ticker)
    sentiment_data = fetch_free_sentiment(ticker)
    fundamentals = fetch_fundamentals(ticker)
    institutional = fetch_institutional(ticker)
    analyst = fetch_analyst_views(ticker)

    news_text = ""
    if news:
        news_text = "\n".join(
            f"- [{n.get('published_utc', '')}] {n.get('title', '')}"
            for n in news[:5]
        )

    # Serialize whichever options source we actually have: paid sweep flow_data OR
    # the FREE yfinance chain analysis (scores + chain_summary). Previously only
    # flow_data was used, so without Unusual Whales the free options signal was
    # silently dropped and Dimension 6 was always scored as "missing".
    options_text = ""
    options_available = bool(options_flow)
    if options_flow and options_flow.get("flow_data"):
        options_text = json.dumps(options_flow["flow_data"][:10], indent=2)
    elif options_flow and options_flow.get("options_analysis"):
        options_text = json.dumps(options_flow["options_analysis"], indent=2)
    else:
        options_available = False

    sentiment_text = ""
    if sentiment_data and sentiment_data.get("sources_available"):
        sentiment_text = json.dumps(sentiment_data, indent=2, ensure_ascii=False)

    fundamentals_text = json.dumps(fundamentals, indent=2) if fundamentals else ""
    institutional_text = (json.dumps(institutional, indent=2, ensure_ascii=False)
                          if institutional else "")
    analyst_text = (json.dumps(analyst, indent=2, ensure_ascii=False)
                    if analyst else "")

    # Verified sector rotation for Dimension 5: the candidate's OWN sector standing
    # (mapped from its GICS sector → SPDR ETF) plus the market leaders/improving.
    sector_text = ""
    sector_evidence = None
    srot = fetch_sector_rotation() or {}  # full board (memoized) — has per-sector by_etf
    if srot:
        cand_gics = (fundamentals or {}).get("sector")
        cand_etf = gics_to_etf(cand_gics)
        cand_sec = (srot.get("by_etf") or {}).get(cand_etf) if cand_etf else None
        sector_evidence = {
            "candidate_sector": {"gics": cand_gics, "etf": cand_etf, **(cand_sec or {})},
            "market_leaders": srot.get("leaders"),
            "market_improving": srot.get("improving"),
            "as_of": srot.get("as_of"),
        }
        sector_text = json.dumps(sector_evidence, ensure_ascii=False, indent=2)

    evidence_capabilities = safe_build_layer1_capabilities(
        technical_evidence=technical_evidence,
        news=news,
        options_flow=options_flow,
        sentiment=sentiment_data,
        fundamentals=fundamentals,
        institutional=institutional,
        sector=sector_evidence,
        analyst=analyst,
        regime_context=regime_context,
        source_configuration={
            "polygon_news": bool(os.environ.get("POLYGON_API_KEY")),
            "unusual_whales": bool(os.environ.get("UNUSUAL_WHALES_API_KEY")),
        },
    )

    candidate_json = json.dumps(candidate, indent=2, default=str)

    user_msg = f"""Score the following candidate using the 7-dimension framework (100 pts total).

## Regime Context
{json.dumps(regime_context, indent=2)}

## Candidate Data
{candidate_json}

## Technical Evidence Contract
The `technical_evidence` object in Candidate Data is the only authoritative
source for Dimension 1.
Do not infer or award points for any technical input marked missing.
Score an unsupported pattern as 0 and add its
`technical:<input_name>` token to `data_missing`. Do not reconstruct missing
facts from summaries, rank scores, or prose.

## Recent News
{news_text if news_text else "No recent news available."}

## Options Flow Data
{options_text if options_text else "No options flow data available — score Dimension 6 as 0 and mark data_missing."}

## Social Sentiment — free sources (StockTwits + Reddit/ApeWisdom)
{sentiment_text if sentiment_text else "No free sentiment data available — score Dimension 3 conservatively and mark data_missing."}
Use this as the primary input for Dimension 3 (Sentiment, 0-13). HEED the calibration_note: StockTwits skews structurally bullish, so reward RELATIVE signals (high message volume, a real bearish share, Reddit mention momentum) — not default bullishness. Judge whether buzz looks organic or coordinated and whether any high-follower / smart-money accounts are involved.

## Fundamentals — free (yfinance: valuation / profitability / growth / health / analyst estimates)
{fundamentals_text if fundamentals_text else "No fundamentals available."}
Use this verified data to ground the catalyst/quality read; do not invent ratios.

## Institutional & Insider Activity — free (yfinance, SEC 13F + Form-4 derived)
{institutional_text if institutional_text else "No institutional/insider data available — score Dimension 4 conservatively and mark data_missing."}
Use this as the PRIMARY input for Dimension 4 (Institutional / 籌碼, 0-10): weight institutional ownership %, notable holder pctChange, and insider net buying/selling. Do NOT guess this dimension when data is present.

## Analyst Consensus — free (yfinance: ratings / price targets / upgrades-downgrades / estimate revisions)
{analyst_text if analyst_text else "No analyst data available — score Dimension 7 conservatively and mark data_missing."}
Use this as the PRIMARY input for Dimension 7 (Analyst Consensus / 分析師共識, 0-8): rating distribution (strongBuy/buy skew), price_targets.upside_pct (mean target vs spot), and recent_actions (dated upgrades / PT raises) plus estimate_revisions (up_last_30d vs down_last_30d). Weight rating MOMENTUM (recent upgrades, PT raises, net-up estimate revisions) over the static consensus — targets are a lagging/anchoring signal. If analyst views contradict the technical/options read, say so in key_risks. Do NOT guess this dimension when data is present.

## Sector Rotation — free (yfinance sector-ETF RRG, RS-Ratio/RS-Momentum vs SPY)
{sector_text if sector_text else "No sector rotation data available — score Dimension 5a conservatively and mark data_missing."}
Use this as the PRIMARY, VERIFIED input for Dimension 5a (Sector RS, 0-2): score the candidate by its OWN sector's quadrant (candidate_sector.quadrant) — Leading=2, Improving or Weakening=1, Lagging=0 — corroborated by candidate_sector.excess_20d (sector return minus SPY). Do NOT guess sector strength; use these numbers. (5b market regime still comes from SPY/VIX in Regime Context.)

## Historical Case Library Reference
{case_library[:2000] if case_library else "No case library loaded."}

Set `risk_vetoes` to `["bearish_options_flow"]` only when the supplied options
data explicitly proves put sweeps above $2M in five days, or put/call volume
above 1.8 together with aggressive bid-side puts. Aggregate yfinance put/call
volume without aggressor evidence does not prove this veto. Otherwise return [].

Return ONLY a valid JSON object matching this exact schema:
All human-readable string fields must be written in Traditional Chinese:
technical_breakdown values, key_signals, key_risks, suggested_entry_zone,
suggested_stop, similar_to_case explanations, and anti_example_warning.
{{
  "ticker": "{ticker}",
  "as_of_date": "{regime_context.get('scan_date', '')}",
  "verdict": "REJECT | WATCHLIST | NEEDS_LAYER_2",
  "composite_score": <int 0-100>,
  "regime_adjusted_score": <float>,
  "scores": {{
    "technical": <int 0-30>,
    "catalyst": <int 0-16>,
    "sentiment": <int 0-13>,
    "institutional": <int 0-10>,
    "sector_market": <int 0-3>,
    "options_flow": <int 0-20>,
    "analyst": <int 0-8>
  }},
  "technical_breakdown": {{
    "trend_template": <float>,
    "volume": <int>,
    "pattern": <int>,
    "pattern_type": "<string>",
    "macd_confirmation": <int>,
    "macd_state": "<string>"
  }},
  "key_signals": ["<string>", ...],
  "key_risks": ["<string>", ...],
  "suggested_entry_zone": "<string>",
  "suggested_stop": "<string>",
  "suggested_size_pct": <float>,
  "similar_to_case": "<string or null>",
  "anti_example_warning": "<string or null>",
  "novel_pattern": <bool>,
  "risk_vetoes": ["bearish_options_flow"],
  "data_missing": ["<string>", ...],
  "due_diligence_required": <bool>
}}"""

    try:
        # cache_system=True: the screener rubric (~5.6k tokens) is identical for every
        # candidate, so caching it bills the prompt once per 5-min TTL and reads it
        # cheaply for the other ~250 — the bulk of the daily subscription usage.
        resp = llm.chat(system=screener_prompt, user=user_msg, max_tokens=4096,
                        cache_system=True)
        result = _extract_json(resp)
        return _finalize_candidate_result(
            result,
            regime_context,
            options_available=options_available,
            sentiment_available=bool(sentiment_text),
            institutional_available=bool(institutional_text),
            analyst_available=bool(analyst_text),
            scoring_mode="full",
            technical_evidence=technical_evidence,
            evidence_capabilities=evidence_capabilities,
        )
    except Exception as e:
        print(f"[llm_score] Error scoring {ticker}: {e}", file=sys.stderr)
        return {
            "ticker": ticker,
            "verdict": "REJECT",
            "composite_score": 0,
            "regime_adjusted_score": 0,
            "scoring_mode": scoring_mode,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM response text."""
    # Try direct parse
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last ``` lines
        start = 1
        end = len(lines) - 1
        for i, line in enumerate(lines):
            if line.strip().startswith("```") and i > 0:
                end = i
                break
        text = "\n".join(lines[start:end])

    # Find JSON object boundaries
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("No JSON object found in response")

    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace_start : i + 1])

    raise ValueError("Malformed JSON in response")


def should_defer_candidate_error(message: str) -> bool:
    """True when a candidate should move to end-of-batch retry."""
    msg = (message or "").lower()
    return any(marker in msg for marker in ("timeout", "timed out", "overloaded", "temporarily"))


def progress_message(done_now: int, total: int) -> str:
    return f"Processed {done_now}/{total}"


def normalized_deferred_retries(value: int | None) -> int:
    return max(0, int(value or 0))


def _human_text_values(row: dict) -> list[str]:
    values: list[str] = []
    for key in ("key_signals", "key_risks", "suggested_entry_zone", "suggested_stop"):
        value = row.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    breakdown = row.get("technical_breakdown")
    if isinstance(breakdown, dict):
        values.extend(str(value) for value in breakdown.values() if value)
    for key in ("similar_to_case", "anti_example_warning"):
        value = row.get(key)
        if isinstance(value, dict):
            values.extend(str(v) for v in value.values() if v)
        elif value:
            values.append(str(value))
    return values


def has_english_human_text(row: dict) -> bool:
    text = " ".join(_human_text_values(row))
    without_allowed = re.sub(r"\b[A-Z]{2,6}\b", " ", text)
    return bool(re.search(r"[A-Za-z]{4,}", without_allowed))


def prepare_resume_scores(
    prior_scored: list[dict],
    *,
    rescore_stale_language: bool = False,
) -> tuple[list[dict], set[str], list[dict]]:
    kept: list[dict] = []
    rescore_rows: list[dict] = []
    for row in prior_scored:
        ticker = row.get("ticker")
        if rescore_stale_language and ticker and has_english_human_text(row):
            rescore_rows.append(row)
        else:
            kept.append(row)
    done_tickers = {row.get("ticker") for row in kept if row.get("ticker")}
    return kept, done_tickers, rescore_rows


def merge_rescore_fallbacks(rescore_rows: list[dict], newly: list[dict]) -> list[dict]:
    new_tickers = {row.get("ticker") for row in newly if row.get("ticker")}
    return [row for row in rescore_rows if row.get("ticker") not in new_tickers]


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_scored_output(universe: dict, regime_context: dict, scored: list[dict],
                        min_score: int) -> dict:
    """Build the scored_candidates.json payload from current partial results."""
    ordered = list(scored)
    ordered.sort(key=lambda x: x.get("regime_adjusted_score", 0), reverse=True)
    total = len(universe.get("tickers", []) or [])
    remaining = total - len(ordered)
    needs_layer2 = [s for s in ordered if s.get("verdict") == "NEEDS_LAYER_2"]
    watchlist = [s for s in ordered if s.get("verdict") == "WATCHLIST"]
    rejected = [s for s in ordered if s.get("verdict") == "REJECT"]

    output = {
        "scan_date": regime_context.get("scan_date") or universe.get("scan_date") or _utc_date(),
        "generated_at": _utc_timestamp(),
        "regime_context": regime_context,
        "universe_size": universe.get("total_universe", 0),
        "passed_hard_filters": universe.get("passed_hard_filters", 0),
        "total_candidates": total,
        "scored_candidates_count": len(ordered),
        "remaining_unscored": remaining,
        "needs_layer2_count": len(needs_layer2),
        "watchlist_count": len(watchlist),
        "rejected_count": len(rejected),
        "min_score_threshold": min_score,
        "needs_layer2": needs_layer2,
        "watchlist": watchlist,
        "all_scored": ordered,
    }
    output["promotion_reachability_v1"] = safe_summarize_run(
        ordered,
        multiplier=regime_context.get("global_score_multiplier"),
        total_candidates=total,
    )
    return output


def write_scored_output(path: str | Path, universe: dict, regime_context: dict,
                        scored: list[dict], min_score: int) -> dict:
    """Atomically write scored_candidates.json, safe for partial progress."""
    output = build_scored_output(universe, regime_context, scored, min_score)
    out_path = Path(path)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    tmp.replace(out_path)
    return output


def write_scored_snapshot(output: dict, history_dir: str | Path) -> Path:
    """Write a dated score snapshot for analytics history."""
    scan_date = str(output.get("scan_date") or _utc_date())
    path = Path(history_dir)
    path.mkdir(parents=True, exist_ok=True)
    out = path / f"{scan_date}.json"
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    tmp.replace(out)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage 2: LLM Scoring")
    parser.add_argument("--input", required=True, help="filtered_universe.json")
    parser.add_argument("--prompt", required=True, help="Path to screener prompt .md")
    parser.add_argument("--min-score", type=int, default=65)
    parser.add_argument("--provider", default="codex", choices=["auto", "codex"])
    parser.add_argument("--model", default=None,
                        help="Optional Codex model; defaults to CODEX_MODEL/account setting")
    parser.add_argument("--layer1-model", default=None,
                        help="Optional Codex model for the Layer-1 breadth scan; "
                             "falls back to --model/account setting.")
    parser.add_argument("--limit", "--max-candidates", type=int, default=None,
                        dest="limit", help="Score at most N (unscored) candidates "
                        "this run — for batching across runs/sessions.")
    parser.add_argument("--resume", action="store_true",
                        help="Skip tickers already in --output and merge; reuse the "
                             "stored regime_context. Lets you score in batches.")
    parser.add_argument("--rescore-stale-language", action="store_true",
                        help="When resuming, rescore prior rows whose human-readable "
                             "fields still use an older language format.")
    parser.add_argument("--output", default="scored_candidates.json")
    parser.add_argument("--history-dir", default="reports/candidate_scores",
                        help="write dated scoring snapshot for analytics; set empty to disable")
    parser.add_argument("--case-library", default=None,
                        help="Path to 06_historical_case_library.md")
    parser.add_argument("--status-file",
                        help="write latest run status JSON for local UI progress")
    parser.add_argument("--candidate-retries", type=int,
                        default=int(os.environ.get("CANDIDATE_RETRIES", "3")),
                        help="LLM retry attempts per candidate before deferring")
    parser.add_argument("--deferred-retries", type=int,
                        default=int(os.environ.get("CANDIDATE_DEFERRED_RETRIES", "1")),
                        help="end-of-run retries for transiently deferred candidates; "
                             "0 leaves them for the next --resume run")
    parser.add_argument("--scoring-mode", choices=["full", "fast"],
                        default=os.environ.get("CANDIDATE_SCORING_MODE", "full"),
                        help="full uses all enrichment blocks; fast uses compact "
                             "hard-filter-only prompts for local subscription runs")
    args = parser.parse_args()

    # Load inputs
    with open(args.input) as f:
        universe = json.load(f)
    status = RunStatus(args.status_file) if args.status_file else None

    screener_prompt = Path(args.prompt).read_text(encoding="utf-8")

    case_library = ""
    if args.case_library and Path(args.case_library).exists():
        case_library = Path(args.case_library).read_text(encoding="utf-8")
    else:
        # Try default location
        default_case = Path("system_prompts/06_historical_case_library.md")
        if default_case.exists():
            case_library = default_case.read_text(encoding="utf-8")

    score_model = args.layer1_model or args.model
    llm = LLMClient(provider=args.provider, model=score_model,
                    retry_max_attempts=args.candidate_retries)

    # Resume: load prior output, skip already-scored tickers, reuse regime.
    prior_scored, done_tickers, regime_context = [], set(), None
    rescore_rows = []
    if args.resume and Path(args.output).exists():
        try:
            prior = json.load(open(args.output))
            prior_scored = prior.get("all_scored", [])
            prior_scored, done_tickers, rescore_rows = prepare_resume_scores(
                prior_scored,
                rescore_stale_language=args.rescore_stale_language,
            )
            regime_context = prior.get("regime_context")
            print(f"[llm_score] Resume: {len(done_tickers)} already scored, "
                  "reusing stored regime_context." if regime_context else
                  f"[llm_score] Resume: {len(done_tickers)} already scored.")
            if rescore_rows:
                print(f"[llm_score] Rescoring {len(rescore_rows)} stale-language rows: "
                      f"{', '.join(str(r.get('ticker')) for r in rescore_rows[:10])}")
        except Exception as e:
            print(f"[llm_score] Resume read failed ({e}); starting fresh.", file=sys.stderr)

    # Layer 0: Regime context (compute once; reuse on resume)
    if regime_context is None:
        print("[llm_score] Computing regime context (Layer 0) ...")
        if status:
            status.update_stage(
                "llm_score.regime",
                "計算大盤 regime",
                progress_pct=0,
                message="Computing regime context",
            )
        market_data = enrich_with_market_data(universe.get("tickers", []))
        regime_context = compute_regime_context(llm, screener_prompt, market_data)
        if status:
            status.update_stage(
                "llm_score.regime",
                "計算大盤 regime",
                status="succeeded",
                progress_pct=100,
                message="Regime context ready",
            )
    elif status:
        status.update_stage(
            "llm_score.regime",
            "計算大盤 regime",
            status="succeeded",
            progress_pct=100,
            message="Reused stored regime_context",
        )
    print(f"[llm_score] Regime: VIX={regime_context.get('vix_level')}, "
          f"multiplier={regime_context.get('global_score_multiplier')}")

    # Layer 1: score the next batch of UNSCORED candidates
    all_candidates = universe.get("tickers", [])
    pending = [c for c in all_candidates if c.get("ticker") not in done_tickers]
    batch = pending[:args.limit] if args.limit else pending
    total = len(all_candidates)
    print(f"[llm_score] {len(done_tickers)} done · scoring {len(batch)} this run "
          f"· {len(pending) - len(batch)} will remain · model={score_model} "
          f"mode={args.scoring_mode}")
    if status:
        status.update_stage(
            "llm_score.candidates",
            "Codex 評分候選",
            progress_pct=0,
            message=f"Scoring 0/{len(batch)}",
            metrics={
                "candidate_limit": args.limit,
                "scoring_mode": args.scoring_mode,
                "total_candidates": total,
                "already_scored": len(done_tickers),
                "scored_candidates": len(prior_scored),
                "remaining_candidates": len(pending),
            },
        )

    newly = []
    errored = []
    deferred = []

    def _persist_partial() -> list[dict]:
        scored_now = prior_scored + merge_rescore_fallbacks(rescore_rows, newly) + newly
        write_scored_output(args.output, universe, regime_context, scored_now, args.min_score)
        return scored_now

    def _status_progress(done_now: int, message: str) -> None:
        if not status:
            return
        pct = done_now / max(len(batch), 1) * 100
        status.update_stage(
            "llm_score.candidates",
            "Codex 評分候選",
            progress_pct=pct,
            message=message,
            metrics={
                "scored_candidates": len(prior_scored) + len(newly),
                "errored_candidates": len(errored),
                "deferred_candidates": len(deferred),
                "remaining_candidates": max(0, len(pending) - done_now),
            },
        )

    for i, cand in enumerate(batch):
        ticker = cand["ticker"]
        print(f"  [{i+1}/{len(batch)}] Scoring {ticker} ...")
        res = score_candidate(llm, screener_prompt, regime_context,
                              cand, case_library, scoring_mode=args.scoring_mode)
        # A transient failure (e.g. timeout/rate-limit after retries) must NOT be
        # persisted as a finished REJECT — otherwise --resume skips it forever.
        # Leave it out of all_scored so the next batch retries it.
        if res.get("error"):
            if should_defer_candidate_error(res.get("error", "")):
                deferred.append(cand)
                print(f"[llm_score] Deferring {ticker} to end-of-batch retry: "
                      f"{res.get('error')}", file=sys.stderr)
            else:
                errored.append(ticker)
        else:
            newly.append(res)
            _persist_partial()
        _status_progress(i + 1, progress_message(i + 1, len(batch)))
        if llm.provider == "codex":
            time.sleep(0.5)

    deferred_retry_count = normalized_deferred_retries(args.deferred_retries)
    retry_queue = list(deferred)
    if retry_queue and deferred_retry_count == 0:
        print(f"[llm_score] {len(retry_queue)} deferred this run (not retried now; "
              "will retry on resume): "
              f"{', '.join(c.get('ticker', '?') for c in retry_queue)}",
              file=sys.stderr)
    for retry_round in range(1, deferred_retry_count + 1):
        if not retry_queue:
            break
        current_retry = retry_queue
        retry_queue = []
        for j, cand in enumerate(current_retry, start=1):
            ticker = cand["ticker"]
            print(f"  [retry {retry_round}.{j}/{len(current_retry)}] Scoring {ticker} ...")
            res = score_candidate(llm, screener_prompt, regime_context,
                                  cand, case_library, scoring_mode=args.scoring_mode)
            if res.get("error"):
                if retry_round < deferred_retry_count and should_defer_candidate_error(
                    res.get("error", "")
                ):
                    retry_queue.append(cand)
                else:
                    errored.append(ticker)
            else:
                newly.append(res)
                _persist_partial()
            _status_progress(len(batch), f"Retried deferred {j}/{len(current_retry)}")
            if llm.provider == "codex":
                time.sleep(0.5)

    if errored:
        print(f"[llm_score] {len(errored)} errored this run (not persisted, will "
              f"retry on resume): {', '.join(errored)}", file=sys.stderr)

    output = write_scored_output(
        args.output,
        universe,
        regime_context,
        prior_scored + merge_rescore_fallbacks(rescore_rows, newly) + newly,
        args.min_score,
    )
    snapshot_path = write_scored_snapshot(output, args.history_dir) if args.history_dir else None
    scored = output["all_scored"]
    remaining = output["remaining_unscored"]
    needs_layer2 = output["needs_layer2"]
    watchlist = output["watchlist"]
    rejected = [s for s in scored if s.get("verdict") == "REJECT"]

    if status:
        status.succeed(
            message=f"{len(scored)} candidates scored; {remaining} remaining",
            metrics={
                "candidate_limit": args.limit,
                "scoring_mode": args.scoring_mode,
                "scored_candidates": len(scored),
                "remaining_candidates": remaining,
                "needs_layer2_count": len(needs_layer2),
                "watchlist_count": len(watchlist),
                "rejected_count": len(rejected),
            },
            outputs={
                "ranked_candidates": {"path": args.input, "exists": Path(args.input).exists()},
                "scored_candidates": {"path": args.output, "exists": True, "stale": False},
                "candidate_scores": {
                    "path": str(snapshot_path) if snapshot_path else "",
                    "exists": bool(snapshot_path and snapshot_path.exists()),
                    "stale": False,
                },
            },
        )

    print(f"[llm_score] Done: {len(needs_layer2)} NEEDS_LAYER_2, "
          f"{len(watchlist)} WATCHLIST, {len(rejected)} REJECT · "
          f"scored {len(scored)}/{total} · {remaining} remaining → {args.output}")


if __name__ == "__main__":
    main()
