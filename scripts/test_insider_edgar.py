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


def test_parse_form4_garbage():
    assert ie._parse_form4("not xml at all") == (0.0, 0, 0)
    assert ie._parse_form4("") == (0.0, 0, 0)


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
