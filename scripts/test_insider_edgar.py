#!/usr/bin/env python3
"""Self-contained tests for insider_edgar Form-4 parsing (no network).

The error-prone part is the XML parse: Form-4 amounts are NESTED
(<transactionShares><value>N</value></transactionShares>) and only open-market
codes P/S count. These exercise that logic on a synthetic ownership document.

Run:  .venv/bin/python scripts/test_insider_edgar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import insider_edgar as ie  # noqa: E402

# A synthetic Form-4: one open-market BUY (P), one SELL (S), one GRANT (A, ignored).
# Amounts are nested under <value> exactly like real SEC ownership XML.
_FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>50.0</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>400</value></transactionShares>
        <transactionPricePerShare><value>50.0</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>99999</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


def test_parse_form4_nested_values():
    net, n_buy, n_sell = ie._parse_form4(_FORM4)
    # P 1000×50 = +50000 ; S 400×50 = -20000 ; A (grant) ignored → net 30000
    assert net == 30000.0, net
    assert n_buy == 1 and n_sell == 1, (n_buy, n_sell)


def test_parse_form4_ignores_non_open_market():
    xml = _FORM4.replace("<transactionCode>P</transactionCode>",
                         "<transactionCode>M</transactionCode>")  # option exercise
    net, n_buy, n_sell = ie._parse_form4(xml)
    # only the S remains as open-market → -20000, 0 buys, 1 sell
    assert net == -20000.0 and n_buy == 0 and n_sell == 1, (net, n_buy, n_sell)


def test_parse_form4_garbage_fails_closed():
    """Unparseable XML is NOT 'no transactions' — it must return None so the
    caller fails the whole ticker closed (Codex TF-1 H2)."""
    assert ie._parse_form4("not xml at all") is None
    assert ie._parse_form4("") is None
    # A VALID Form-4 with zero open-market transactions is real data → (0, 0, 0).
    ok = "<ownershipDocument><documentType>4</documentType></ownershipDocument>"
    assert ie._parse_form4(ok) == (0.0, 0, 0)


def test_malformed_open_market_amounts_fail_closed():
    """An open-market P/S row with missing/non-numeric shares or price must fail
    the DOCUMENT closed (None) — silently skipping it would undercount and could
    flip the net sign, then be cached for a day (Codex TF-1 H2b regression)."""
    bad_price = _FORM4.replace(
        "<transactionPricePerShare><value>50.0</value></transactionPricePerShare>",
        "<transactionPricePerShare><value>not-a-number</value></transactionPricePerShare>", 1)
    assert ie._parse_form4(bad_price) is None
    missing_shares = _FORM4.replace(
        "<transactionShares><value>1000</value></transactionShares>",
        "<transactionShares></transactionShares>", 1)
    assert ie._parse_form4(missing_shares) is None
    # Garbage amounts on a NON-open-market row (grant) stay irrelevant — the A row
    # is skipped before amounts are read, so the P+S still parse normally.
    bad_grant = _FORM4.replace(
        "<transactionShares><value>99999</value></transactionShares>",
        "<transactionShares><value>junk</value></transactionShares>")
    assert ie._parse_form4(bad_grant) == (30000.0, 1, 1)


def test_amendment_fails_closed():
    """An in-window Form 4/A AMENDS an earlier Form 4 (correcting shares/price/
    code or withdrawing rows). Until amendment-aware replacement exists, naively
    summing the originals can flip the net sign — the ticker must fail closed
    (Codex TF-1 r12 regression)."""
    orig_cik, orig_recent, orig_get = ie._cik_for, ie._recent_form4, ie._get
    ie._cik_for = lambda t: "0000000001"
    ie._recent_form4 = lambda cik, days: [
        {"form": "4", "accession": "0000000001-26-000001", "doc": "form4.xml",
         "date": "2026-06-09"},
        {"form": "4/A", "accession": "0000000001-26-000002", "doc": "form4a.xml",
         "date": "2026-06-10"},
    ]
    ie._get = lambda url: (_ for _ in ()).throw(AssertionError("must not fetch"))
    try:
        assert ie._compute("XXX", 30) is None
    finally:
        ie._cik_for, ie._recent_form4, ie._get = orig_cik, orig_recent, orig_get


def test_fetch_failure_fails_closed(monkeypatch):
    """A Form-4 XML that can't be fetched must fail the TICKER closed (None) —
    skipping it would undercount and could flip the net sign, then be cached for
    a day (Codex TF-1 H2 regression)."""
    orig_cik, orig_recent, orig_get = ie._cik_for, ie._recent_form4, ie._get
    ie._cik_for = lambda t: "0000000001"
    ie._recent_form4 = lambda cik, days: [
        {"form": "4", "accession": "0000000001-26-000001", "doc": "form4.xml",
         "date": "2026-06-09"},
        {"form": "4", "accession": "0000000001-26-000002", "doc": "form4.xml",
         "date": "2026-06-10"},
    ]

    def _boom(url):
        raise RuntimeError("SEC transient 503")

    ie._get = _boom
    try:
        assert ie._compute("XXX", 30) is None       # fetch failure → None, not ±$
        # Malformed feed entry (no doc) must also fail closed.
        ie._recent_form4 = lambda cik, days: [
            {"accession": "0000000001-26-000001", "doc": None, "date": "2026-06-09"}]
        assert ie._compute("XXX", 30) is None
    finally:
        ie._cik_for, ie._recent_form4, ie._get = orig_cik, orig_recent, orig_get


def test_form4_xml_url_strips_render_prefix():
    url = ie._form4_xml_url("0001045810", "0001045810-26-000012",
                            "xslF345X06/wf-form4_123.xml")
    assert url.endswith("/000104581026000012/wf-form4_123.xml"), url
    assert "xslF345X06" not in url
    assert ie._form4_xml_url("123", "", "x.xml") is None  # missing accession → None


def test_insider_net_edgar_unknown_ticker(monkeypatch):
    # Force CIK lookup to miss → None (never raises, no network beyond the cik map).
    orig = ie._cik_for
    ie._cik_for = lambda t: None
    try:
        assert ie._compute("ZZZZNOTATICKER", 30) is None
    finally:
        ie._cik_for = orig


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, t in tests:
        try:
            t(None) if t.__code__.co_argcount else t()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
