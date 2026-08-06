#!/usr/bin/env python3
"""Focused no-pytest contracts for UX-0/UX-1A history and UX-1B forward safety."""

from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ui_ux_inventory as inventory  # noqa: E402


EXPECTED_GROUPS = ["今日決策", "市場背景", "研究驗證", "資料維護", "幣圈"]
EXPECTED_TARGETS = {
    "analytics-db",
    "ibkr-reconcile",
    "knowledge-graph",
    "market-thesis",
    "options-cockpit",
    "options-flow",
    "radar",
    "retro-analysis",
    "stock-checkup",
    "theme-flow",
    "trade-state",
    "us-cot",
    "us-screener",
}
BASELINE_PATH = ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-baseline.json"
BASELINE_MARKDOWN_PATH = ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-baseline.md"
CLASSIFICATION_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1a-classification.json"
)
UX1A_CONTRACT_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1a-contract.json"
)
UX1B_PLAN_PATH = (
    ROOT / "docs" / "superpowers" / "plans"
    / "2026-07-16-quant-radar-ui-ux-ux1b.md"
)
UX1B_PRECHANGE_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-prechange.json"
)
UX1B_CLASSIFICATION_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-classification.json"
)
UX1B_ROLLBACK_ROOT = ROOT / ".claude" / "ui_snapshots" / "ux1b" / "rollback-source"
BASELINE_SHA256 = "cec8135ca49aba1859c96635865de72f88993f6aa838fca72da3301a5aff6930"
BASELINE_MARKDOWN_SHA256 = (
    "d70c49f820b6bd8bcb421b49a033dac80b11414142903515665d9dbde4cbb478"
)
UX1A_CLASSIFICATION_SHA256 = (
    "364515dd67ecb82ac5ce1f0b73bd8399bdfb31e654314f143e1f9f1c03a10f9c"
)
UX1A_CONTRACT_SHA256 = (
    "5085e9a1cce20ca0b0fd58dda623436cce48ebc0302398bb073318dfabe36a5b"
)
UX1B_ACCEPTED_PLAN_SHA256 = (
    "48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7"
)
UX1B_PRECHANGE_SHA256 = (
    "38443c1483b03f7bf6bdc5095da161059e7f06e8859d9ba7f1d282413e50d674"
)
UX1B_PENDING_CLASSIFICATION_SHA256 = (
    "c6c27801ffbd7aeffd86514156ba2e4c81f0699b78e6db7278dfdf72d3d6a77b"
)
UX1B_PAGE_PROJECTION_SHA256 = (
    "539bf737382a0f35aca3daaec681aa520152e1381a442904c73d3c61d416f015"
)
UX1B_READY_MARKERS_SHA256 = (
    "9117f0cc9768f66293234a281ef8ae8cc7e9d89b51066cc9220003cfb90235a6"
)
UX1B_ROLLBACK_MANIFEST_SHA256 = (
    "739df8db110428ff6cfe08b405524d17bd56fbbf52427de128e8b805165b3d69"
)
UX1B_ROLLBACK_OWNER_SHA256 = (
    "b1ca8a82cd967cf7b45a54985e4f0a9344b38cfbcf7bb1abba54bff4f60993d8"
)
UX1B_PRIMARY_CLASSIFICATIONS = {"ordinary_interaction", "danger_destructive"}
UX1B_PRIMARY_PRIMITIVES = {
    "button",
    "download_button",
    "form_submit_button",
    "link_button",
}
CODEX_DIAGNOSTIC_ADDITIONS = frozenset(
    {
        "ui/_candidate_controls.py|_render_codex_auth_status|st.caption|d269c45f5a780e95ece62a97e4d741401a1520f4fc00b55749249b51b56ccb11|1",
        "ui/_candidate_controls.py|_render_codex_auth_status|st.markdown|4972a3d534acc7cc11141147e208773a22ce3a1a18173d75621ce2ada152d1f4|1",
        "ui/us_cot.py|_render_codex_auth_status|st.caption|d269c45f5a780e95ece62a97e4d741401a1520f4fc00b55749249b51b56ccb11|1",
        "ui/us_cot.py|_render_codex_auth_status|st.markdown|326bde26dc3a4a6c52d256cc83c188541cbade099ea478f703c5ebf24c85a900|1",
        "ui/watchlist_categorize.py|render|st.warning|a646c5c23acfc4cc698b5c53c8988d19f34bf9e5fec085e018348867d6fb63fe|1",
        "ui/x_sentiment.py|_render_free_first_status|st.code|c765b9c44dcc1ad670440682a3b6e1e7732f38cd60adf51f85010c4772088a21|1",
        "ui/x_sentiment.py|_render_paid_grok_refresh|st.error|6de464045e294850c3638359ee156cc9aa6352b8fe0348e572fa51f705f9df7a|1",
        "ui/x_sentiment.py|_render_social_ai_codex_auth_status|st.caption|d269c45f5a780e95ece62a97e4d741401a1520f4fc00b55749249b51b56ccb11|1",
        "ui/x_sentiment.py|_render_social_ai_codex_auth_status|st.markdown|326bde26dc3a4a6c52d256cc83c188541cbade099ea478f703c5ebf24c85a900|1",
    }
)
CODEX_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/_candidate_controls.py|_render_claude_auth_status|st.markdown|4972a3d534acc7cc11141147e208773a22ce3a1a18173d75621ce2ada152d1f4|1",
        "ui/_fundamentals.py|render_fundamentals|st.caption|88c50f84797c15991f941eb86c233c08ebe8da3cbf71f82b44d9d18a0233cefb|1",
        "ui/us_cot.py|_render_claude_auth_status|st.markdown|a370560502b09d823f980e7fb314e4f27f18ef160fa83d81a77630c2e0fdb3db|1",
        "ui/watchlist_categorize.py|render|st.warning|decfa6cba07be253889e5a5d2b6040d443a708129d6dc4b014abbe368e43f177|1",
        "ui/x_sentiment.py|_render_free_first_status|st.caption|f0ec55b9c3b45907be6481d56cbd3fe65867723bf08ad8236f56baa4d2302dcc|1",
        "ui/x_sentiment.py|_render_free_first_status|st.code|d53ae7a6cac8120350f535755870ccfe65bd81199311d41f01fb8403bb01b97c|1",
        "ui/x_sentiment.py|_render_free_first_status|st.markdown|bf44b2a16e11e59258231f249b5b7b2f32a425ce5dd7d99e884d57af746062bb|1",
        "ui/x_sentiment.py|_render_paid_grok_refresh|persistence.dumps|31bfebacface154b2d554798c84b3bb54a06c2e462d096746ad976488be90e8a|1",
        "ui/x_sentiment.py|_render_paid_grok_refresh|persistence.write_text|a3158b85c4f4ef08bee61639320754e7ce8de79a40634c2b738ab43202356a32|1",
        "ui/x_sentiment.py|_render_paid_grok_refresh|st.error|7f610eccc51c889767ec6bfe734b278cbbd56c70ef75296da6013b8bdeabd8cd|1",
        "ui/x_sentiment.py|_render_paid_grok_refresh|st.warning|cdc7fcaa971331305d1b2be8303d23cd9c7ea15373c6751733222b8f0f3ced1a|1",
        "ui/x_sentiment.py|_render_radar|st.info|016a5e1d1fc50499260aad170bca116e453834700df9259085f59a583a503285|1",
        "ui/x_sentiment.py|_render_single|st.info|d9078670b172899b5bbb5cd0001ceeefbf3910e1c4bbce27bc63abf58578585c|1",
        "ui/x_sentiment.py|_render_social_ai_claude_auth_status|st.markdown|a370560502b09d823f980e7fb314e4f27f18ef160fa83d81a77630c2e0fdb3db|1",
    }
)
PHASE3A_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/sys_ai_updates.py|_read_local_updates|LOGGER.warning|d4952272fa9424d090739533f877b308fd101b2a4eb832e9ba7332eefc6152b2|1",
    }
)
PHASE3A_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    123,
    "4977be526cdcea02752953170b170a958338c756cfeca9ce023849cd1dd96497",
)
PHASE3B_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/sys_schedules.py|_read_local_schedules|LOGGER.warning|baf3e1b0a4b1dddd11f27347e41f67bb434341b555ee5c1e1c87d7f3029ed320|1",
    }
)
PHASE3B_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    124,
    "9b0b524d0012218b7081d73729ea27223a26a697f69ed5255c53eb0f376ff396",
)
PHASE3C_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/institution_portfolio.py|_read_local_fund_catalog|LOGGER.warning|6844a58c39d240ae75e80d0b5dcb2dca2de31036591215b8ac6325ea0077fe84|1",
    }
)
PHASE3C_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    135,
    "8dbf42b6a4a8fb7b6af136628edb071154af433237dcabd7010532f2617edd9f",
)
PHASE3D_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/us_options.py|_load_iv_history|LOGGER.warning|7870ceddf19a51ca20da1be0c752e826308c209ef0a33617b5c0c5a3dfe70dc5|1",
    }
)
PHASE3D_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    116,
    "7ba44a445a75022f1d8ca46f4208895b970e2489c0abc2acc82331cd051773ec",
)
PHASE3E_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/options_flow.py|_read_local_options_flow|LOGGER.warning|d38ce25ca4cbaf5a0f88dc55f92241aab6f018839bb6d7384cbbb2ca6b180363|1",
    }
)
PHASE3E_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    126,
    "a184cbd4bdf9ed5acd38ce8f73b3899147a4c317031f5bc2355dd0e96aa9bdc8",
)
PHASE4C_DIAGNOSTIC_ADDITIONS = frozenset(
    {
        "ui/crypto_universe.py|render|st.download_button.data|8726e64edefddb6e54287331192e512ee9417669ea451011f412b14a07ecbce8|1",
    }
)
PHASE4C_DIAGNOSTIC_ADDITION_RECEIPT = (
    1,
    120,
    "9e69b62d29bdc2e9338c55be8cb136f474bf33c5394bec3495b1f953e58d3cbf",
)
PHASE4C_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/crypto_universe.py|render|st.download_button.data|b44e602f8aafac19e8a26dfc38162b4e9371886966436ec61be6a39256c77c67|1",
        "ui/crypto_universe.py|render|st.download_button.data|c69a6a101fa5428d90ec58cca607c87c6a44cfbe09acb64812346a4eaf24ad88|1",
    }
)
PHASE4C_DIAGNOSTIC_REMOVAL_RECEIPT = (
    2,
    240,
    "d417bf1d29efcea747c379daf483d0c9d6b43cf008440ea7b45bd5b9315ea8e3",
)
PHASE4H_DIAGNOSTIC_ADDITIONS = frozenset(
    {
        "ui/institutional_holdings.py|_render_score_context|st.expander|6994d81b3397110fa246d61490437cbd06e12a2a805a0436a0b7bfcf9e89317c|1",
    }
)
PHASE4H_DIAGNOSTIC_ADDITION_RECEIPT = (
    1,
    130,
    "47672b2fc0a269119ebdf53d997f5e9fb17d913ac0dbcad7600e0ef541982fcb",
)
PHASE4H_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/institutional_holdings.py|_render_score_context|st.expander|f994014e9d7a1051d38b0efb6d7101d6842e52c28aaedcee76c0f6b3f368dbdf|1",
    }
)
PHASE4H_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    130,
    "f7038e4222bc489619388b42325c557eefd65a464ba5f8fd162ce3ced377c8bb",
)
PHASE4S_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/us_screener.py|render|collection.append|0b8726d4c3635f2176fe602e1903c8ee345ccb32cfdaff550c12a3861f190bfa|1",
        "ui/us_screener.py|render|collection.append|25220c84e5d056b8c4d533369583d3f5aff0564281806f79b4def3cf69777530|1",
        "ui/us_screener.py|render|collection.append|28e3d3c08945c98df874aa150dd2c7c3a8c6ad3ee71f13af04324bf0ee335ee9|1",
    }
)
PHASE4S_DIAGNOSTIC_REMOVAL_RECEIPT = (
    3,
    330,
    "4a8b09f860db5ff862ff12494b868ee0067c1ea776509295e6a901efeeb56092",
)
PHASE5E_DIAGNOSTIC_ADDITIONS = frozenset(
    {
        "ui/options_cockpit.py|_render_direction_vol|st.caption|40ed57446d8b2042c60d6f11b94a67975087edaf409d0f842263c339bb7c666f|1",
    }
)
PHASE5E_DIAGNOSTIC_ADDITION_RECEIPT = (
    1,
    122,
    "4246f57223baeb0e705bda4e6097138ad30b3bf808a551eaa2b432f75ea49a35",
)
PHASE5E_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/options_cockpit.py|_render_direction_vol|st.caption|ae42959cde67ef69a9861571f6c4b4f5be2db3942c71234dbb072ee94d6e4df0|1",
    }
)
PHASE5E_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    122,
    "9a5c37881a04384de6be4fe5f6127a2d7770f15377081b5546bf2be73254b177",
)
PHASE5H_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/market_thesis.py|_render_regime_reference|collection.append|ad282788913471bea3d662105bf8ee0947282adee5d15436c479809567a57bc9|1",
    }
)
PHASE5H_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    130,
    "0340eb2d8990f5d30c5d88d6c95486dd88fff36ec4c981f17a7ca5e1e6dbad28",
)
PHASE5N_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/oversold_reversal_lane.py|_render_forward_validation|collection.append|91c3904bda7fd126d3e7df6cc400ce3ceef8459f171f962bd4336733b2b8b960|1",
    }
)
PHASE5N_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    141,
    "d2ce2dded2e652f87af2afad8293b82c85ad6f474cc3938c62d81f944c52e984",
)
PHASE5X_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/sys_schedules.py|_latest_report_result|collection.append|1cb6db79015ce406a3ca107e0ecbf7c66de09c400aeeb5094997bc759d967d02|1",
    }
)
PHASE5X_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    127,
    "0a8251295969abbca140112d274b02f8f5a86a7cb84dcc6ca2b631cef494077d",
)
PHASE6C_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/continuation_validation.py|render|st.caption|ce1ca7f3e97c944cc9af302aafc3dc05b0c3175a27ed6e29f53a14c77b615a42|1",
        "ui/continuation_validation.py|render|st.error|c041380584a8409dc019628d4c0487c974569a6940618384be3348b964fdfe5b|1",
        "ui/continuation_validation.py|render|st.warning|b5cf7328ac7560396cb3f4c664137adab729f63ac0f423c65093b60825b97fca|1",
    }
)
PHASE6C_DIAGNOSTIC_REMOVAL_RECEIPT = (
    3,
    343,
    "88fbaea4d966fded2ff8139b25cd9be8d9c2e2bd031a2b4ee409cb5591037d8f",
)
PHASE6F_DIAGNOSTIC_ADDITIONS = frozenset(
    {
        "ui/us_cot.py|render|st.json|6c6abcaaff87c1b683fad78ad78e519c60dfe1e4f4c42d828582e9fd202098e4|1",
    }
)
PHASE6F_DIAGNOSTIC_ADDITION_RECEIPT = (
    1,
    95,
    "91a21566d7010af1bb2d0440d4b1e21f2ddb694faca0f9d4f61d3fa50056a42b",
)
PHASE6F_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/us_cot.py|render|collection.append|0056d14ab21620fd5a9bdd585593cc4a15a760b10df674aac382dbe0267b28ba|1",
        "ui/us_cot.py|render|collection.append|0dfef9f29624b5d65b6f6d43af772f11ce6e5245715ffc7f2cac4c346db12b41|1",
        "ui/us_cot.py|render|st.caption|5150876bb3c1a2f9194a2765e53377f7c4b39d1d7c81ba70c50f37e491d88f46|1",
        "ui/us_cot.py|render|st.json|724a3b59cb910454cc41f5bbb82ae0fe53ba2a9d57e6eeeb3d670df9380d7a49|1",
        "ui/us_cot.py|render|st.markdown|17bb691e64ba3a7698b7a424807f6568c0a98045ee014c6f2121572cc53ba4f0|1",
        "ui/us_cot.py|render|st.markdown|d30af3d5c6ee1a7c1141e24563d5d86c76aa8708a1f5d0613cd23c93ab01b580|1",
        "ui/us_cot.py|render|st.warning|9863d97a45c904ec750c6bf2ccadb5c9baf147599d64c4787a26ea9f5892d351|1",
    }
)
PHASE6F_DIAGNOSTIC_REMOVAL_RECEIPT = (
    7,
    699,
    "922796a9ea045416c771b7df8930dec4e375abd685fcabeef40da6cc9d34dd62",
)
PHASE6I_DIAGNOSTIC_REMOVALS = frozenset(
    {
        "ui/knowledge_graph.py|_node_table|collection.append|73af9b2a02d7d78df577d6c3988bf7fe211d4a5d35fda519a438fd049d51afd8|1",
    }
)
PHASE6I_DIAGNOSTIC_REMOVAL_RECEIPT = (
    1,
    119,
    "af159d817c07865ec07be30e2e754f3ce2a71a3f3b445aba97d0a2947bded3a1",
)
CODEX_PRIMARY_ADDITIONS = frozenset(
    {
        "ui/_candidate_controls.py|_render_codex_auth_status|st.link_button|constant|bc187ef8b988326f738182bfa7136994ea859d7f2849354b4840d80622c303df|1",
        "ui/us_cot.py|_render_codex_auth_status|st.link_button|constant|3016d6a98cb5f8ad872c932d3f4fdc1417073a815c3ffd81cc25f697025ef3f3|1",
        "ui/us_cot.py|_render_generate|c1.button|constant|ebab6bc21cef4428e5f0fbf312cfa6c4f55adc323a15762ec210eedd66a3733c|1",
        "ui/x_sentiment.py|_render_social_ai_codex_auth_status|st.link_button|constant|3016d6a98cb5f8ad872c932d3f4fdc1417073a815c3ffd81cc25f697025ef3f3|1",
    }
)
CODEX_PRIMARY_REMOVALS = frozenset(
    {
        "ui/us_cot.py|_render_claude_auth_status|st.link_button|constant|3db51caf50ab54a311f6849b516bbbcae90c1293a0f144186e64c4db6b646b18|1",
        "ui/us_cot.py|_render_generate|c1.button|constant|1bf6a8c6a3fb722607080d967be37b979e22a7c440274569378ee62e80b6611c|1",
        "ui/x_sentiment.py|_render_social_ai_claude_auth_status|st.link_button|constant|3db51caf50ab54a311f6849b516bbbcae90c1293a0f144186e64c4db6b646b18|1",
    }
)
CODEX_MIGRATION_RECEIPTS = {
    "diagnostic_additions": (
        9,
        1_112,
        "b5b83165e1bcb8cbd63e8c002e79454b08f0e62c5a566f8c42a74af3fd371dc2",
    ),
    "diagnostic_removals": (
        14,
        1_699,
        "16335375241385b055ee387b0d08a9b417a5d8e90169ef431c0046b3451744a7",
    ),
    "primary_additions": (
        4,
        534,
        "8a0d8d5aa873d6902eeb0dfa287e7d7a39ae616183da38e5caa1ffa9949f9fe3",
    ),
    "primary_removals": (
        3,
        393,
        "04bd4a0ca75cbb14917498613b4195345f79921581cf6e621f44cc080438bccf",
    ),
}
UX1B_PALETTE = {
    "border.focus": "#7fe3f0",
    "interactive.accent": "#60a5fa",
    "interactive.active": "#1e40af",
    "interactive.control": "#3b82f6",
    "interactive.disabled": "#6b7280",
    "interactive.hover": "#1d4ed8",
    "interactive.primary": "#2563eb",
    "text.disabled": "#8b93a7",
    "text.on-primary": "#ffffff",
}
UNSAFE_CLASSIFICATIONS = {
    "static_retained",
    "shared_dynamic_escaped",
    "removed_ux1a",
    "deferred_ux4",
}
DIAGNOSTIC_CLASSIFICATIONS = {"fixed", "safe", "false_positive", "deferred"}
UX1A_INVENTORY_TARGET_FILES = {
    "ui/_candidate_controls.py",
    "ui/_components.py",
    "ui/_design.py",
    "ui/_shared.py",
    "ui/ai_chat.py",
    "ui/institution_portfolio.py",
    "ui/sys_ai_updates.py",
    "ui/sys_schedules.py",
    "ui/today_decision.py",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(inventory.canonical_json(value).encode("utf-8")).hexdigest()


def _flatten_buckets(
    buckets: dict[str, list[str]], expected: set[str]
) -> tuple[list[str], dict[str, str]]:
    assert set(buckets) == expected
    site_ids: list[str] = []
    by_site: dict[str, str] = {}
    for classification in sorted(buckets):
        values = buckets[classification]
        assert values == sorted(values)
        for site_id in values:
            assert isinstance(site_id, str) and site_id
            assert site_id not in by_site
            site_ids.append(site_id)
            by_site[site_id] = classification
    return site_ids, by_site


def _sources() -> tuple[str, dict[str, str]]:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_sources = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "ui").rglob("*.py"))
    }
    return app_source, ui_sources


def _expect_assertion(action: Callable[[], object]) -> None:
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("expected an assertion failure")


def _node_qualname(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _node_qualname(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _primary_expression_category(node: ast.AST) -> str:
    categories = {
        ast.BinOp: "binary",
        ast.Call: "call",
        ast.Constant: "constant",
        ast.Dict: "dict",
        ast.JoinedStr: "f_string",
        ast.List: "list",
        ast.Name: "name",
        ast.Set: "set",
        ast.Subscript: "subscript",
        ast.Tuple: "tuple",
    }
    for node_type, label in categories.items():
        if isinstance(node, node_type):
            return label
    return re.sub(r"(?<!^)(?=[A-Z])", "_", type(node).__name__).lower()


def _scan_primary_actions(
    app_source: str, ui_sources: Mapping[str, str]
) -> list[dict[str, object]]:
    """Return exact location-free identities for direct type='primary' actions."""

    records: list[dict[str, object]] = []
    sources = [("app.py", app_source), *sorted(ui_sources.items())]
    for relative_path, source in sources:
        try:
            tree = ast.parse(source, filename=relative_path, type_comments=True)
        except SyntaxError as exc:
            raise inventory.InventoryError(
                f"{relative_path}: invalid Python at line {exc.lineno or '?'}"
            ) from None

        stack: list[str] = []

        class PrimaryVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            def visit_Call(self, node: ast.Call) -> None:
                call_kind = _node_qualname(node.func) or type(node.func).__name__
                primitive = call_kind.rsplit(".", 1)[-1]
                keywords = [item for item in node.keywords if item.arg == "type"]
                if primitive not in UX1B_PRIMARY_PRIMITIVES:
                    if any(
                        isinstance(item.value, ast.Constant)
                        and item.value.value == "primary"
                        for item in keywords
                    ):
                        raise inventory.InventoryError(
                            f"unsupported type='primary' action primitive: {primitive}"
                        )
                    self.generic_visit(node)
                    return
                if primitive in UX1B_PRIMARY_PRIMITIVES and any(
                    item.arg is None for item in node.keywords
                ):
                    raise inventory.InventoryError(
                        "primary action type cannot be hidden in **kwargs"
                    )
                if not keywords:
                    self.generic_visit(node)
                    return
                if len(keywords) != 1:
                    raise inventory.InventoryError("action must have exactly one type keyword")
                type_value = keywords[0].value
                if not (
                    isinstance(type_value, ast.Constant)
                    and isinstance(type_value.value, str)
                ):
                    raise inventory.InventoryError("action type must be a string literal")
                if type_value.value != "primary":
                    self.generic_visit(node)
                    return
                label = node.args[0] if node.args else next(
                    (item.value for item in node.keywords if item.arg == "label"), None
                )
                if label is None:
                    raise inventory.InventoryError("primary action label is required")
                fingerprint = hashlib.sha256(
                    ast.dump(
                        node, annotate_fields=True, include_attributes=False
                    ).encode("utf-8")
                ).hexdigest()
                records.append(
                    {
                        "call_kind": call_kind,
                        "expression_category": _primary_expression_category(label),
                        "file": relative_path,
                        "fingerprint": fingerprint,
                        "function": ".".join(stack) if stack else "<module>",
                        "review_line": node.lineno,
                    }
                )
                self.generic_visit(node)

        PrimaryVisitor().visit(tree)

    records.sort(
        key=lambda item: (
            str(item["file"]),
            int(item["review_line"]),
            str(item["function"]),
            str(item["call_kind"]),
            str(item["fingerprint"]),
        )
    )
    occurrences: defaultdict[tuple[str, ...], int] = defaultdict(int)
    for item in records:
        key = (
            str(item["file"]),
            str(item["function"]),
            str(item["call_kind"]),
            str(item["expression_category"]),
            str(item["fingerprint"]),
        )
        occurrences[key] += 1
        item["occurrence"] = occurrences[key]
        item["site_id"] = "|".join((*key, str(occurrences[key])))
    return records


def _validate_primary_action_ledger(
    classification: Mapping[str, object],
    app_source: str,
    ui_sources: Mapping[str, str],
) -> None:
    scope = classification["scope"]
    assert isinstance(scope, Mapping)
    assert scope["primary_action_primitives"] == sorted(UX1B_PRIMARY_PRIMITIVES)
    assert scope["primary_site_id_version"] == "full-call-ast/v1"
    buckets = classification["primary_actions"]
    assert isinstance(buckets, dict)
    classified, _by_site = _flatten_buckets(
        buckets, UX1B_PRIMARY_CLASSIFICATIONS
    )
    assert buckets["danger_destructive"] == []
    current = _scan_primary_actions(app_source, ui_sources)
    current_ids = sorted(str(item["site_id"]) for item in current)
    assert len(current_ids) == len(set(current_ids))
    assert len(current_ids) == 20
    assert len(classified) == len(set(classified)) == 19
    _assert_exact_codex_delta(
        set(current_ids),
        set(classified),
        additions=CODEX_PRIMARY_ADDITIONS,
        removals=CODEX_PRIMARY_REMOVALS,
        addition_receipt=CODEX_MIGRATION_RECEIPTS["primary_additions"],
        removal_receipt=CODEX_MIGRATION_RECEIPTS["primary_removals"],
    )


def _canonical_site_id_receipt(site_ids: set[str]) -> tuple[int, int, str]:
    assert all(isinstance(site_id, str) and site_id for site_id in site_ids)
    payload = "".join(f"{site_id}\n" for site_id in sorted(site_ids)).encode(
        "utf-8"
    )
    return len(site_ids), len(payload), hashlib.sha256(payload).hexdigest()


def _assert_exact_codex_delta(
    current: set[str],
    parent: set[str],
    *,
    additions: frozenset[str],
    removals: frozenset[str],
    addition_receipt: tuple[int, int, str],
    removal_receipt: tuple[int, int, str],
) -> None:
    observed_additions = current - parent
    observed_removals = parent - current
    assert observed_additions == additions
    assert observed_removals == removals
    assert _canonical_site_id_receipt(observed_additions) == addition_receipt
    assert _canonical_site_id_receipt(observed_removals) == removal_receipt


def _expect_inventory_error(action: Callable[[], object], needle: str) -> None:
    try:
        action()
    except inventory.InventoryError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected error containing {needle!r}, got {exc!r}") from exc
    else:
        raise AssertionError(f"expected InventoryError containing {needle!r}")


def _page_projection(result: Mapping[str, object]) -> list[dict[str, object]]:
    pages = result["pages"]
    assert isinstance(pages, list)
    return [
        {
            "callable": page["callable"],
            "nav_title": page["title"],
            "registry_key": page["registry_key"],
            "route": page["route"],
        }
        for page in pages
    ]


def _validate_sha_size_record(record: object) -> None:
    assert isinstance(record, Mapping)
    assert set(record) == {"sha256", "size"}
    assert re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"]))
    assert isinstance(record["size"], int) and not isinstance(record["size"], bool)
    assert record["size"] >= 0


def _validate_ux1b_prechange(
    prechange: Mapping[str, object], classification: Mapping[str, object]
) -> None:
    assert set(prechange) == {
        "accepted_plan",
        "captured_at",
        "created_files",
        "file_sets",
        "frozen_page_projection",
        "hash_algorithm",
        "palette",
        "planned_existing_files",
        "protected",
        "ready_markers",
        "rollback_source",
        "schema_version",
        "worktree",
    }
    assert prechange["schema_version"] == "quant-radar-ui-ux-ux1b-prechange/v1"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", str(prechange["captured_at"]))
    assert prechange["accepted_plan"] == {
        "path": "docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b.md",
        "sha256": UX1B_ACCEPTED_PLAN_SHA256,
        "size": UX1B_PLAN_PATH.stat().st_size,
    }
    assert _sha256(UX1B_PLAN_PATH) == UX1B_ACCEPTED_PLAN_SHA256
    assert classification["accepted_plan"] == {
        "path": prechange["accepted_plan"]["path"],  # type: ignore[index]
        "sha256": UX1B_ACCEPTED_PLAN_SHA256,
    }

    assert prechange["hash_algorithm"] == {
        "aggregate": "sha256(sorted(repo_relative_posix_path + NUL + file_sha256 + NUL + decimal_size + LF))",
        "file": "sha256(raw_bytes)",
    }
    assert prechange["palette"] == UX1B_PALETTE

    file_sets = prechange["file_sets"]
    assert isinstance(file_sets, Mapping)
    assert set(file_sets) == {
        "documentation_modify",
        "production_runtime_batch",
        "test_fixture_tool_create",
        "test_fixture_tool_modify",
    }
    for paths in file_sets.values():
        assert isinstance(paths, list) and paths == sorted(paths)
        assert len(paths) == len(set(paths))
        assert all(isinstance(path, str) and path for path in paths)
    assert file_sets["production_runtime_batch"] == [
        ".streamlit/config.toml",
        "app.py",
        "requirements.txt",
        "ui/_design.py",
    ]
    planned = prechange["planned_existing_files"]
    assert isinstance(planned, Mapping)
    assert set(planned) == (
        set(file_sets["production_runtime_batch"])
        | set(file_sets["test_fixture_tool_modify"])
        | set(file_sets["documentation_modify"])
    )
    for record in planned.values():
        _validate_sha_size_record(record)

    created = prechange["created_files"]
    assert isinstance(created, Mapping)
    assert set(created) == {
        "docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json",
        "docs/ui-ux/quant-radar-ui-v2-ux1b-prechange.json",
        "docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json",
        "docs/ui-ux/quant-radar-ui-v2-ux1b.md",
        "scripts/test_ui_ux_theme.py",
        "scripts/test_ui_ux_theme_matrix.py",
        "scripts/ui_ux_theme_fixture_app.py",
        "scripts/ui_ux_theme_matrix.py",
    }
    assert created["docs/ui-ux/quant-radar-ui-v2-ux1b-prechange.json"] == {
        "initial_exists": False,
        "self_hash_omitted": True,
        "task0_created": True,
    }
    pending_record = created["docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json"]
    assert pending_record == {
        "initial_exists": False,
        "sha256": UX1B_PENDING_CLASSIFICATION_SHA256,
        "size": 4316,
        "task0_created": True,
    }
    if classification["state"] == "pending":
        assert _sha256(UX1B_CLASSIFICATION_PATH) == pending_record["sha256"]
        assert UX1B_CLASSIFICATION_PATH.stat().st_size == pending_record["size"]

    frozen = prechange["frozen_page_projection"]
    assert isinstance(frozen, Mapping)
    assert set(frozen) == {"canonical_sha256", "records", "source"}
    assert frozen["source"] == (
        "docs/ui-ux/quant-radar-ui-v2-baseline.json::contract.pages"
    )
    assert frozen["canonical_sha256"] == UX1B_PAGE_PROJECTION_SHA256
    assert _canonical_sha256(frozen["records"]) == UX1B_PAGE_PROJECTION_SHA256
    live_projection = _page_projection(inventory.build_inventory(ROOT))
    assert frozen["records"] == live_projection
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert frozen["records"] == _page_projection(baseline["contract"])

    markers = prechange["ready_markers"]
    assert isinstance(markers, list) and len(markers) == 27
    assert _canonical_sha256(markers) == UX1B_READY_MARKERS_SHA256
    assert [marker["registry_key"] for marker in markers] == [
        page["registry_key"] for page in live_projection
    ]
    for marker in markers:
        assert set(marker) == {"exact", "level", "registry_key", "text"}
        assert isinstance(marker["exact"], bool)
        assert marker["level"] in {1, 2}
        assert isinstance(marker["text"], str) and marker["text"]

    worktree = prechange["worktree"]
    assert isinstance(worktree, Mapping)
    assert set(worktree) == {
        "status_bytes",
        "status_entry_count",
        "status_lines",
        "status_sha256",
    }
    status_bytes = ("\n".join(worktree["status_lines"]) + "\n").encode("utf-8")
    assert len(status_bytes) == worktree["status_bytes"]
    assert len(worktree["status_lines"]) == worktree["status_entry_count"]
    assert hashlib.sha256(status_bytes).hexdigest() == worktree["status_sha256"]

    protected = prechange["protected"]
    assert isinstance(protected, Mapping)
    assert set(protected) == {"aggregate_groups", "explicit_files"}
    for record in protected["explicit_files"].values():
        _validate_sha_size_record(record)
    for record in protected["aggregate_groups"].values():
        assert set(record) == {"bytes", "file_count", "sha256"}
        assert isinstance(record["bytes"], int) and record["bytes"] >= 0
        assert isinstance(record["file_count"], int) and record["file_count"] > 0
        assert re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
    explicit = protected["explicit_files"]
    assert explicit[CLASSIFICATION_PATH.relative_to(ROOT).as_posix()]["sha256"] == UX1A_CLASSIFICATION_SHA256
    assert explicit[UX1A_CONTRACT_PATH.relative_to(ROOT).as_posix()]["sha256"] == UX1A_CONTRACT_SHA256


def _validate_ux1b_rollback(
    prechange: Mapping[str, object], classification: Mapping[str, object]
) -> None:
    rollback = prechange["rollback_source"]
    assert rollback == {
        "manifest_path": ".claude/ui_snapshots/ux1b/rollback-source/manifest.json",
        "manifest_sha256": UX1B_ROLLBACK_MANIFEST_SHA256,
        "owner_path": ".claude/ui_snapshots/ux1b/rollback-source/.quant-radar-ux1b-owner",
        "owner_sha256": UX1B_ROLLBACK_OWNER_SHA256,
    }
    manifest_path = ROOT / rollback["manifest_path"]
    owner_path = ROOT / rollback["owner_path"]
    assert manifest_path.parent.resolve() == UX1B_ROLLBACK_ROOT.resolve()
    assert owner_path.parent.resolve() == UX1B_ROLLBACK_ROOT.resolve()
    assert _sha256(manifest_path) == UX1B_ROLLBACK_MANIFEST_SHA256
    assert _sha256(owner_path) == UX1B_ROLLBACK_OWNER_SHA256
    assert owner_path.read_text(encoding="utf-8") == "quant-radar-ui-ux-ux1b\n"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {
        "accepted_plan", "created_at", "files", "owner", "schema_version"
    }
    assert manifest["schema_version"] == "quant-radar-ui-ux-ux1b-rollback/v1"
    assert manifest["owner"] == "quant-radar-ui-ux-ux1b"
    assert manifest["accepted_plan"] == classification["accepted_plan"]
    expected_backups = {
        ".streamlit/config.toml": "config.toml",
        "app.py": "app.py",
        "requirements.txt": "requirements.txt",
        "ui/_design.py": "_design.py",
    }
    assert {path: item["backup"] for path, item in manifest["files"].items()} == expected_backups
    planned = prechange["planned_existing_files"]
    for source, backup_name in expected_backups.items():
        record = manifest["files"][source]
        assert set(record) == {"backup", "sha256", "size"}
        assert record["backup"] == Path(backup_name).name == backup_name
        backup = UX1B_ROLLBACK_ROOT / backup_name
        assert backup.parent.resolve() == UX1B_ROLLBACK_ROOT.resolve()
        assert _sha256(backup) == record["sha256"]
        assert backup.stat().st_size == record["size"]
        assert not backup.is_symlink()
        assert backup.stat().st_mode & 0o777 == 0o644
        assert {"sha256": record["sha256"], "size": record["size"]} == planned[source]
        if classification["state"] == "pending":
            live = ROOT / source
            assert not live.is_symlink()
            assert live.stat().st_mode & 0o777 == 0o644
            if source == "requirements.txt":
                assert record == {
                    "backup": "requirements.txt",
                    "sha256": (
                        "123fd3ee1559a93cf1e30efcf327dd93"
                        "f6e8604cfa1a6a13487d6de6f3da7d16"
                    ),
                    "size": 426,
                }
                assert _sha256(live) == (
                    "1ab5cc81e8e3aab7a3b48b80449087dd"
                    "f250d22b12b1a8b9b4f5e46b0e790138"
                )
                assert live.stat().st_size == 351
            else:
                assert _sha256(live) == record["sha256"]
                assert live.stat().st_size == record["size"]


def _trusted_css_delta_ids(classification: Mapping[str, object]) -> set[str]:
    unsafe = classification["unsafe_html"]
    assert isinstance(unsafe, Mapping) and set(unsafe) == {"trusted_static_theme_css"}
    records = unsafe["trusted_static_theme_css"]
    assert isinstance(records, list)
    if classification["state"] == "pending":
        assert records == []
        return set()
    assert classification["state"] == "accepted"
    assert len(records) == 1
    record = records[0]
    assert set(record) == {
        "builder", "expression_fingerprint", "rationale_code", "site_id"
    }
    assert record["builder"] == "_design.build_global_theme_css"
    assert record["rationale_code"] == "trusted_static_theme_css"
    assert re.fullmatch(r"[0-9a-f]{64}", record["expression_fingerprint"])
    assert isinstance(record["site_id"], str) and record["site_id"]
    return {record["site_id"]}


def _validate_ux1b_forward_projection(
    classification: Mapping[str, object], current_inventory: Mapping[str, object]
) -> None:
    assert set(classification) == {
        "accepted_plan",
        "parent",
        "primary_actions",
        "rationales",
        "schema_version",
        "scope",
        "state",
        "unsafe_html",
    }
    assert classification["schema_version"] == (
        "quant-radar-ui-ux-ux1b-classification/v1"
    )
    assert classification["state"] in {"pending", "accepted"}
    assert classification["accepted_plan"] == {
        "path": "docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b.md",
        "sha256": UX1B_ACCEPTED_PLAN_SHA256,
    }
    assert classification["parent"] == {
        "ux1a_classification": {
            "path": "docs/ui-ux/quant-radar-ui-v2-ux1a-classification.json",
            "sha256": UX1A_CLASSIFICATION_SHA256,
        },
        "ux1a_contract": {
            "path": "docs/ui-ux/quant-radar-ui-v2-ux1a-contract.json",
            "sha256": UX1A_CONTRACT_SHA256,
        },
    }
    assert classification["rationales"] == {
        "danger_destructive": (
            "Destructive actions cannot use the globally styled ordinary primary variant."
        ),
        "ordinary_interaction": (
            "Reviewed non-destructive interaction rendered with type='primary'."
        ),
        "trusted_static_theme_css": (
            "Module-scope no-argument builder using only immutable approved design tokens."
        ),
    }
    scope = classification["scope"]
    assert set(scope) == {
        "planned_trusted_site",
        "primary_action_primitives",
        "primary_site_id_version",
        "protected_parent_metric_site_id",
        "source_roots",
    }
    assert scope["source_roots"] == ["app.py", "ui/**/*.py"]
    assert scope["planned_trusted_site"] == {
        "builder": "_design.build_global_theme_css",
        "call_kind": "st.markdown",
        "expression": "_design.build_global_theme_css()",
        "file": "app.py",
        "function": "<module>",
    }

    ux1a_contract = json.loads(UX1A_CONTRACT_PATH.read_text(encoding="utf-8"))
    parent_current = ux1a_contract["current_contract"]
    parent_unsafe = set(parent_current["unsafe_site_ids"])
    parent_diagnostics = set(parent_current["diagnostic_site_ids"])
    metric_ids = {
        site_id for site_id in parent_unsafe
        if site_id.startswith("app.py|<module>|st.markdown|constant|")
    }
    assert len(metric_ids) == 1
    assert scope["protected_parent_metric_site_id"] == next(iter(metric_ids))

    current = inventory.baseline_contract(current_inventory)
    compatibility = {
        key: current[key] for key in inventory.UX0_COMPATIBILITY_FIELDS
    }
    assert _canonical_sha256(compatibility) == parent_current["compatibility_sha256"]
    current_diagnostics = {
        item["site_id"] for item in current["diagnostics"]
    }
    assert len(current_diagnostics) == 154
    assert not (current_diagnostics & PHASE3A_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE3B_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE3C_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE3D_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE3E_DIAGNOSTIC_REMOVALS)
    assert current_diagnostics & PHASE4C_DIAGNOSTIC_ADDITIONS == (
        PHASE4C_DIAGNOSTIC_ADDITIONS
    )
    assert not (current_diagnostics & PHASE4C_DIAGNOSTIC_REMOVALS)
    assert current_diagnostics & PHASE4H_DIAGNOSTIC_ADDITIONS == (
        PHASE4H_DIAGNOSTIC_ADDITIONS
    )
    assert not (current_diagnostics & PHASE4H_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE4S_DIAGNOSTIC_REMOVALS)
    assert current_diagnostics & PHASE5E_DIAGNOSTIC_ADDITIONS == (
        PHASE5E_DIAGNOSTIC_ADDITIONS
    )
    assert not (current_diagnostics & PHASE5E_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE5H_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE5N_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE5X_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE6C_DIAGNOSTIC_REMOVALS)
    assert current_diagnostics & PHASE6F_DIAGNOSTIC_ADDITIONS == (
        PHASE6F_DIAGNOSTIC_ADDITIONS
    )
    assert not (current_diagnostics & PHASE6F_DIAGNOSTIC_REMOVALS)
    assert not (current_diagnostics & PHASE6I_DIAGNOSTIC_REMOVALS)
    assert (
        _canonical_site_id_receipt(PHASE3A_DIAGNOSTIC_REMOVALS)
        == PHASE3A_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE3B_DIAGNOSTIC_REMOVALS)
        == PHASE3B_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE3C_DIAGNOSTIC_REMOVALS)
        == PHASE3C_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE3D_DIAGNOSTIC_REMOVALS)
        == PHASE3D_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE3E_DIAGNOSTIC_REMOVALS)
        == PHASE3E_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE4C_DIAGNOSTIC_ADDITIONS)
        == PHASE4C_DIAGNOSTIC_ADDITION_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE4C_DIAGNOSTIC_REMOVALS)
        == PHASE4C_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE4H_DIAGNOSTIC_ADDITIONS)
        == PHASE4H_DIAGNOSTIC_ADDITION_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE4H_DIAGNOSTIC_REMOVALS)
        == PHASE4H_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE4S_DIAGNOSTIC_REMOVALS)
        == PHASE4S_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE5E_DIAGNOSTIC_ADDITIONS)
        == PHASE5E_DIAGNOSTIC_ADDITION_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE5E_DIAGNOSTIC_REMOVALS)
        == PHASE5E_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE5H_DIAGNOSTIC_REMOVALS)
        == PHASE5H_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE5N_DIAGNOSTIC_REMOVALS)
        == PHASE5N_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE5X_DIAGNOSTIC_REMOVALS)
        == PHASE5X_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE6C_DIAGNOSTIC_REMOVALS)
        == PHASE6C_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE6F_DIAGNOSTIC_ADDITIONS)
        == PHASE6F_DIAGNOSTIC_ADDITION_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE6F_DIAGNOSTIC_REMOVALS)
        == PHASE6F_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    assert (
        _canonical_site_id_receipt(PHASE6I_DIAGNOSTIC_REMOVALS)
        == PHASE6I_DIAGNOSTIC_REMOVAL_RECEIPT
    )
    _assert_exact_codex_delta(
        (
            current_diagnostics
            - PHASE4C_DIAGNOSTIC_ADDITIONS
            - PHASE4H_DIAGNOSTIC_ADDITIONS
            - PHASE5E_DIAGNOSTIC_ADDITIONS
            - PHASE6F_DIAGNOSTIC_ADDITIONS
        )
        | PHASE3A_DIAGNOSTIC_REMOVALS
        | PHASE3B_DIAGNOSTIC_REMOVALS
        | PHASE3C_DIAGNOSTIC_REMOVALS
        | PHASE3D_DIAGNOSTIC_REMOVALS
        | PHASE3E_DIAGNOSTIC_REMOVALS
        | PHASE4C_DIAGNOSTIC_REMOVALS
        | PHASE4H_DIAGNOSTIC_REMOVALS
        | PHASE4S_DIAGNOSTIC_REMOVALS
        | PHASE5E_DIAGNOSTIC_REMOVALS
        | PHASE5H_DIAGNOSTIC_REMOVALS
        | PHASE5N_DIAGNOSTIC_REMOVALS
        | PHASE5X_DIAGNOSTIC_REMOVALS
        | PHASE6C_DIAGNOSTIC_REMOVALS
        | PHASE6F_DIAGNOSTIC_REMOVALS
        | PHASE6I_DIAGNOSTIC_REMOVALS,
        parent_diagnostics,
        additions=CODEX_DIAGNOSTIC_ADDITIONS,
        removals=CODEX_DIAGNOSTIC_REMOVALS,
        addition_receipt=CODEX_MIGRATION_RECEIPTS[
            "diagnostic_additions"
        ],
        removal_receipt=CODEX_MIGRATION_RECEIPTS[
            "diagnostic_removals"
        ],
    )
    current_unsafe = {item["site_id"] for item in current["unsafe_html"]}
    assert not (parent_unsafe - current_unsafe)
    trusted_ids = _trusted_css_delta_ids(classification)
    assert current_unsafe - parent_unsafe == trusted_ids
    if classification["state"] == "accepted":
        trusted_record = classification["unsafe_html"]["trusted_static_theme_css"][0]
        current_by_id = {item["site_id"]: item for item in current["unsafe_html"]}
        site = current_by_id[trusted_record["site_id"]]
        assert site["file"] == "app.py"
        assert site["function"] == "<module>"
        assert site["call_kind"] == "st.markdown"
        assert site["expression_category"] == "call"
        assert site["static"] is False
        assert site["fingerprint"] == trusted_record["expression_fingerprint"]

        app_tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        matching_expressions: list[ast.AST] = []
        for call in (node for node in ast.walk(app_tree) if isinstance(node, ast.Call)):
            unsafe = next(
                (item.value for item in call.keywords if item.arg == "unsafe_allow_html"),
                None,
            )
            if not (isinstance(unsafe, ast.Constant) and unsafe.value is True):
                continue
            expression = call.args[0] if call.args else None
            if expression is None:
                continue
            fingerprint = hashlib.sha256(
                ast.dump(
                    expression, annotate_fields=True, include_attributes=False
                ).encode("utf-8")
            ).hexdigest()
            if fingerprint == trusted_record["expression_fingerprint"]:
                matching_expressions.append(expression)
        assert len(matching_expressions) == 1
        expected_expression = ast.parse(
            "_design.build_global_theme_css()", mode="eval"
        ).body
        assert ast.dump(
            matching_expressions[0], annotate_fields=True, include_attributes=False
        ) == ast.dump(expected_expression, annotate_fields=True, include_attributes=False)

        design_tree = ast.parse((ROOT / "ui" / "_design.py").read_text(encoding="utf-8"))
        builders = [
            node for node in design_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "build_global_theme_css"
        ]
        assert len(builders) == 1
        arguments = builders[0].args
        assert not arguments.posonlyargs
        assert not arguments.args
        assert not arguments.kwonlyargs
        assert arguments.vararg is None
        assert arguments.kwarg is None


def test_repository_page_and_navigation_contract() -> None:
    result = inventory.build_inventory(ROOT)
    pages = result["pages"]
    navigation = result["navigation"]

    assert len(pages) == 27
    assert navigation["groups"] == EXPECTED_GROUPS
    assert len([page for page in pages if page["default"]]) == 1
    default = next(page for page in pages if page["default"])
    assert default["url_path"] == "today-decision"
    assert default["registry_key"] == "today-decision"
    assert default["route"] == "/"
    assert navigation["root_route"] == "/"
    assert navigation["default_registry_key"] == "today-decision"
    assert len(navigation["bookmark_routes"]) == 26
    assert all(route.startswith("/") for route in navigation["bookmark_routes"])
    assert navigation["registry_wiring"] == {
        "navigation_variable": "pg",
        "registry_update": True,
        "selected_page_run": True,
        "source": "nav",
    }


def test_registry_navigation_run_wiring_mutations_fail_closed() -> None:
    app_source, ui_sources = _sources()
    registry_block = (
        "_shared.PAGE_REGISTRY.update(\n"
        "    {p.url_path: p for pages in nav.values() for p in pages})"
    )
    mutations = [
        (app_source.replace(registry_block, ""), "PAGE_REGISTRY.update"),
        (
            app_source.replace(
                registry_block,
                "if False:\n"
                "    _shared.PAGE_REGISTRY.update(\n"
                "        {p.url_path: p for pages in nav.values() for p in pages})",
            ),
            "module scope",
        ),
        (app_source.replace("{p.url_path: p", "{p.title: p"), "p.url_path"),
        (app_source.replace("st.navigation(nav)", "st.navigation(other_nav)"), "st.navigation(nav)"),
        (app_source.replace("pg.run()", "if False:\n    pg.run()"), "module scope"),
        (app_source.replace("pg.run()", "pass  # selected page not run"), ".run()"),
    ]
    for mutated, needle in mutations:
        _expect_inventory_error(
            lambda source=mutated: inventory.analyze_sources(source, ui_sources),
            needle,
        )


def test_page_and_route_mutations_fail_closed() -> None:
    app_source, ui_sources = _sources()

    duplicate_route = app_source.replace(
        'url_path="trade-state"', 'url_path="today-decision"', 1
    )
    _expect_inventory_error(
        lambda: inventory.analyze_sources(duplicate_route, ui_sources), "duplicate"
    )

    lost_default = app_source.replace("default=True, ", "", 1)
    _expect_inventory_error(
        lambda: inventory.analyze_sources(lost_default, ui_sources), "default"
    )

    unresolved_sources = dict(ui_sources)
    unresolved_sources["ui/today_decision.py"] = unresolved_sources[
        "ui/today_decision.py"
    ].replace(
        '_shared.switch_page("trade-state")',
        '_shared.switch_page("missing-page")',
        1,
    )
    _expect_inventory_error(
        lambda: inventory.analyze_sources(app_source, unresolved_sources), "missing-page"
    )

    dynamic_sources = dict(ui_sources)
    dynamic_sources["ui/today_decision.py"] = dynamic_sources[
        "ui/today_decision.py"
    ].replace(
        '_shared.switch_page("trade-state")',
        "_shared.switch_page(target_page)",
        1,
    )
    _expect_inventory_error(
        lambda: inventory.analyze_sources(app_source, dynamic_sources), "dynamic"
    )

    broken_helper_sources = dict(ui_sources)
    broken_helper_sources["ui/_shared.py"] = broken_helper_sources[
        "ui/_shared.py"
    ].replace(
        "st.session_state[state_key] = sym",
        "st.caption('state handoff removed')",
        1,
    )
    _expect_inventory_error(
        lambda: inventory.analyze_sources(app_source, broken_helper_sources),
        "session_state[state_key] write",
    )

    lost_registry_dispatch_sources = dict(ui_sources)
    lost_registry_dispatch_sources["ui/_shared.py"] = lost_registry_dispatch_sources[
        "ui/_shared.py"
    ].replace("st.switch_page(page)", "return True", 1)
    _expect_inventory_error(
        lambda: inventory.analyze_sources(app_source, lost_registry_dispatch_sources),
        "registered page through st.switch_page",
    )

    for unsupported_call in (
        'st.switch_page("stock-checkup")',
        'target_page = "stock-checkup"\nst.switch_page(target_page)',
    ):
        unsupported_sources = dict(ui_sources)
        unsupported_sources["ui/today_decision.py"] += "\n" + unsupported_call + "\n"
        _expect_inventory_error(
            lambda sources=unsupported_sources: inventory.analyze_sources(
                app_source, sources
            ),
            "unsupported switch_page call form",
        )


def test_same_session_route_forms_and_exact_targets() -> None:
    result = inventory.build_inventory(ROOT)
    routes = result["same_session_routes"]
    assert set(routes["forms"]) == {"direct", "jump_helper", "ticker_action_buttons"}
    assert set(routes["targets"]) == EXPECTED_TARGETS
    assert {site["form"] for site in routes["sites"]} == set(routes["forms"])
    registry_keys = {page["registry_key"] for page in result["pages"]}
    assert set(routes["targets"]) <= registry_keys


def test_handoff_keys_preserve_lifecycle_and_operations() -> None:
    result = inventory.build_inventory(ROOT)
    keys = {
        key["key"]: key
        for handoff in result["handoffs"]
        for key in handoff["keys"]
    }
    expected = {
        "checkup_ticker": ("sticky", "write", "get"),
        "checkup_handoff": ("one_shot", "write", "pop"),
        "cockpit_ticker": ("sticky", "write", "get"),
        "radar_handoff": ("one_shot", "write", "pop"),
        "validation_lane": ("one_shot", "write", "pop"),
        "retro_validation_lane": ("sticky", "write", "get"),
        "theme_flow_focus_sector": ("sticky_until_clear", "write", "get"),
    }
    assert set(keys) == set(expected)
    for key_name, (lifecycle, producer, consumer) in expected.items():
        item = keys[key_name]
        assert item["lifecycle"] == lifecycle
        assert item["producer_operation"] == producer
        assert item["consumer_operation"] == consumer
        assert item["producer_sites"]
        assert item["consumer_sites"]
        assert all(site["operation"] == producer for site in item["producer_sites"])
        assert all(site["operation"] == consumer for site in item["consumer_sites"])
        operations = {access["operation"] for access in item["accesses"]}
        assert producer in operations
        assert consumer in operations
    theme_operations = {access["operation"] for access in keys[
        "theme_flow_focus_sector"
    ]["accesses"]}
    assert "pop" in theme_operations


def test_unsafe_html_semantic_ids_are_unique_and_location_free() -> None:
    source = '''
def render():
    st.markdown(build_card(), unsafe_allow_html=True)

    st.markdown(build_card(), unsafe_allow_html=True)
'''
    shifted = "\n\n\n" + source
    first = inventory.scan_ui_source(source, "ui/example.py")["unsafe_html"]
    second = inventory.scan_ui_source(shifted, "ui/example.py")["unsafe_html"]

    assert len(first) == 2
    assert len({item["site_id"] for item in first}) == 2
    assert {item["fingerprint"] for item in first} == {first[0]["fingerprint"]}
    assert [item["occurrence"] for item in first] == [1, 2]
    assert [item["site_id"] for item in first] == [item["site_id"] for item in second]
    assert all(len(item["site_id"].split("|")) == 6 for item in first)


def test_repository_unsafe_inventory_is_deterministic_and_relative() -> None:
    first = inventory.build_inventory(ROOT)
    second = inventory.build_inventory(ROOT)
    sites = first["unsafe_html"]
    assert sites
    assert len({site["site_id"] for site in sites}) == len(sites)
    assert all(not Path(site["file"]).is_absolute() for site in sites)
    diagnostics = first["diagnostics"]
    assert diagnostics
    assert len({site["site_id"] for site in diagnostics}) == len(diagnostics)
    assert all(not Path(site["file"]).is_absolute() for site in diagnostics)
    assert inventory.canonical_json(first) == inventory.canonical_json(second)
    assert str(ROOT) not in inventory.canonical_json(first)

    reordered = copy.deepcopy(first)
    reordered["unsafe_html"].reverse()
    reordered["diagnostics"].reverse()
    reordered["same_session_routes"]["sites"].reverse()
    reordered["handoffs"].reverse()
    for collection in (reordered["unsafe_html"], reordered["diagnostics"]):
        for index, item in enumerate(collection):
            item["review_line"] = 100_000 + index
    for handoff in reordered["handoffs"]:
        handoff["keys"].reverse()
        for key_contract in handoff["keys"]:
            for name in ("accesses", "consumer_sites", "producer_sites"):
                key_contract[name].reverse()
                for index, item in enumerate(key_contract[name]):
                    item["review_line"] = 200_000 + index
    assert inventory.baseline_contract(first) == inventory.baseline_contract(reordered)


def test_versioned_baseline_contract_and_evidence_schema() -> None:
    assert _sha256(BASELINE_PATH) == BASELINE_SHA256
    assert _sha256(BASELINE_MARKDOWN_PATH) == BASELINE_MARKDOWN_SHA256
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["schema_version"] == "quant-radar-ui-ux-baseline/v1"

    current = inventory.baseline_contract(inventory.build_inventory(ROOT))
    assert {
        key: baseline["contract"][key]
        for key in inventory.UX0_COMPATIBILITY_FIELDS
    } == {
        key: current[key]
        for key in inventory.UX0_COMPATIBILITY_FIELDS
    }
    assert "review_line" not in inventory.canonical_json(baseline["contract"])

    evidence = baseline["evidence"]
    assert set(evidence) == {
        "browser_capabilities",
        "captures",
        "console_summary",
        "fixture_revision",
        "manual",
        "mode",
        "pages",
        "selected_browsers",
        "summary",
        "tool_versions",
        "viewports",
        "visual_review",
    }
    assert evidence["fixture_revision"].startswith("quant-radar-ux0-")
    assert evidence["mode"] == "owned deterministic fixture"
    assert set(evidence["tool_versions"]) == {
        "playwright",
        "python",
        "runner",
        "streamlit",
    }
    assert all(
        isinstance(version, str) and version
        for version in evidence["tool_versions"].values()
    )
    pages = evidence["pages"]
    viewports = evidence["viewports"]
    selected = evidence["selected_browsers"]
    capabilities = evidence["browser_capabilities"]
    captures = evidence["captures"]
    summary = evidence["summary"]

    assert pages == [
        "today-decision",
        "trade-state",
        "stock-checkup",
        "options-cockpit",
        "institutions",
        "schedules",
        "ai-updates",
    ]
    assert viewports == [
        {"height": 900, "name": "desktop", "width": 1440},
        {"height": 1024, "name": "tablet", "width": 768},
        {"height": 844, "name": "mobile", "width": 390},
    ]
    assert capabilities["chromium"] == "supported"
    assert capabilities["webkit"] in {"supported", "unsupported"}
    assert "chromium" in selected
    assert len(selected) == len(set(selected))
    assert set(selected) == {
        browser for browser, status in capabilities.items() if status == "supported"
    }
    expected = {
        (browser, page, viewport["name"])
        for browser in selected
        for page in pages
        for viewport in viewports
    }
    actual = {
        (capture["browser"], capture["page"], capture["viewport"])
        for capture in captures
    }
    assert actual == expected
    assert len(actual) == len(captures)
    expected_capture_fields = {
        "blocked_external_request_count",
        "blocked_server_network_count",
        "browser",
        "console_error_count",
        "failed_request_count",
        "fixture_counts",
        "fixture_quiescent",
        "heading_ready",
        "http_errors",
        "metrics",
        "page",
        "page_error_count",
        "route",
        "screenshot",
        "status",
        "streamlit_exception",
        "viewport",
    }
    assert all(set(capture) == expected_capture_fields for capture in captures)
    assert all(capture["status"] == "passed" for capture in captures)
    assert all(capture["heading_ready"] is True for capture in captures)
    assert all(capture["streamlit_exception"] is False for capture in captures)
    assert all(capture["fixture_quiescent"] is True for capture in captures)
    assert all(capture["fixture_counts"] for capture in captures)
    assert all(not Path(capture["screenshot"]).is_absolute() for capture in captures)
    assert all(capture["blocked_external_request_count"] == 0 for capture in captures)
    assert all(capture["blocked_server_network_count"] == 0 for capture in captures)
    assert all(capture["failed_request_count"] == 0 for capture in captures)
    routes = {page["registry_key"]: page["route"] for page in current["pages"]}
    viewport_sizes = {
        viewport["name"]: (viewport["width"], viewport["height"])
        for viewport in viewports
    }
    for capture in captures:
        assert capture["route"] == routes[capture["page"]]
        width, height = viewport_sizes[capture["viewport"]]
        assert capture["metrics"]["viewport_width"] == width
        assert capture["metrics"]["viewport_height"] == height
        metrics = capture["metrics"]
        assert set(metrics) == {
            "document_client_width",
            "document_scroll_height",
            "document_scroll_width",
            "horizontal_overflow",
            "main",
            "plotly_charts",
            "sidebar",
            "sidebar_overlaps_main",
            "viewport_height",
            "viewport_width",
        }
        assert isinstance(metrics["horizontal_overflow"], bool)
        assert isinstance(metrics["sidebar_overlaps_main"], bool)
        assert metrics["document_client_width"] > 0
        assert metrics["document_scroll_width"] >= metrics["document_client_width"]
        assert metrics["document_scroll_height"] > 0
        assert isinstance(metrics["plotly_charts"], int)
        assert metrics["plotly_charts"] >= 0
        for rectangle_name in ("main", "sidebar"):
            rectangle = metrics[rectangle_name]
            assert set(rectangle) == {"height", "visible", "width", "x", "y"}
            assert isinstance(rectangle["visible"], bool)
            assert all(
                isinstance(rectangle[key], (int, float))
                and not isinstance(rectangle[key], bool)
                for key in ("height", "width", "x", "y")
            )
            assert rectangle["height"] > 0
            assert rectangle["width"] > 0
        assert all(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0
            for count in capture["fixture_counts"].values()
        )
        for response in capture["http_errors"]:
            assert set(response) == {"method", "path", "resource_type", "status"}
            assert response["status"] >= 400
            assert response["path"].startswith("/")
            assert "://" not in response["path"]
            assert response["method"] in {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"}
            assert isinstance(response["resource_type"], str) and response["resource_type"]
    assert summary["captures_total"] == len(captures)
    assert summary["captures_passed"] == len(captures)
    assert summary["page_exception_count"] == sum(
        capture["page_error_count"] for capture in captures
    ) == 0
    assert summary["blocked_external_request_count"] == sum(
        capture["blocked_external_request_count"] for capture in captures
    ) == 0
    assert summary["blocked_server_network_count"] == sum(
        capture["blocked_server_network_count"] for capture in captures
    ) == 0
    assert summary["failed_request_count"] == sum(
        capture["failed_request_count"] for capture in captures
    ) == 0
    assert summary["http_error_count"] == sum(
        len(capture["http_errors"]) for capture in captures
    )
    assert summary["console_error_count"] == sum(
        capture["console_error_count"] for capture in captures
    )
    assert summary["console_error_count"] == sum(
        item["count"]
        for item in evidence["console_summary"]
        if item["type"] == "error"
    )
    assert summary["horizontal_overflow_capture_count"] == sum(
        capture["metrics"]["horizontal_overflow"] for capture in captures
    )
    assert summary["sidebar_overlap_capture_count"] == sum(
        capture["metrics"]["sidebar_overlaps_main"] for capture in captures
    )
    assert summary["plotly_chart_count"] == sum(
        capture["metrics"]["plotly_charts"] for capture in captures
    )
    assert summary["streamlit_exception_count"] == sum(
        capture["streamlit_exception"] for capture in captures
    ) == 0
    assert summary["visually_reviewed_capture_count"] == len(captures)
    assert evidence["visual_review"]["screenshots_reviewed"] == len(captures)
    assert set(evidence["visual_review"]) == {
        "findings",
        "review_method",
        "screenshots_reviewed",
        "unexpected_dynamic_content",
    }
    assert evidence["visual_review"]["review_method"] == (
        "Codex image inspection via generated PNGs"
    )
    assert evidence["visual_review"]["findings"]
    assert all(
        set(finding) == {"id", "scope", "severity", "summary"}
        for finding in evidence["visual_review"]["findings"]
    )
    assert evidence["manual"] == {
        "human_usability": "NOT_RUN",
        "safari": "NOT_CHECKED",
    }

    assert evidence["console_summary"]
    for item in evidence["console_summary"]:
        assert set(item) == {"count", "text", "type"}
        assert isinstance(item["count"], int) and item["count"] > 0
        assert isinstance(item["text"], str) and item["text"]
        assert isinstance(item["type"], str) and item["type"]

    summary_fields = {
        "blocked_external_request_count",
        "blocked_server_network_count",
        "captures_passed",
        "captures_total",
        "console_error_count",
        "failed_request_count",
        "horizontal_overflow_capture_count",
        "http_error_count",
        "page_exception_count",
        "plotly_chart_count",
        "sidebar_overlap_capture_count",
        "streamlit_exception_count",
        "visually_reviewed_capture_count",
    }
    assert set(summary) == summary_fields

    def strings(value, key: str | None = None):
        if isinstance(value, dict):
            for child_key, child in value.items():
                yield from strings(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                yield from strings(child, key)
        elif isinstance(value, str):
            yield key, value

    credential = re.compile(
        r"(?i)(?:"
        r"\bBearer\s+[A-Za-z0-9._~+/=-]{6,}|"
        r"\bsk-[A-Za-z0-9_-]{6,}|"
        r"\b[a-z0-9_]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|credential|cookie|authorization)"
        r"\b\s*[:=]\s*[\"']?[^\s,;\"'}]{4,}"
        r")"
    )
    embedded_absolute = re.compile(
        r"(?i)(?:/(?:Users|home|root|tmp|var|private|etc|opt|srv|mnt)/|"
        r"[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+)"
    )
    allowed_url_paths = {capture["route"] for capture in captures} | {
        response["path"]
        for capture in captures
        for response in capture["http_errors"]
    }
    for key, value in strings(evidence):
        if PurePosixPath(value).is_absolute():
            assert key in {"path", "route"} and value in allowed_url_paths, (
                key,
                value,
            )
        assert not PureWindowsPath(value).is_absolute(), (key, value)
        assert not value.startswith(("~/", "~\\")), (key, value)
        assert not embedded_absolute.search(value), (key, value)
        assert not credential.search(value), (key, value)

    encoded = inventory.canonical_json(evidence)
    assert str(ROOT) not in encoded
    assert "captureId" not in encoded
    assert "run_token" not in encoded.lower()


def test_primary_action_full_call_projection_and_mutations_fail_closed() -> None:
    classification = json.loads(UX1B_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    app_source, ui_sources = _sources()
    _validate_primary_action_ledger(classification, app_source, ui_sources)

    shifted_sources = {
        path: "\n\n" + source for path, source in ui_sources.items()
    }
    assert [
        item["site_id"] for item in _scan_primary_actions(app_source, ui_sources)
    ] == [
        item["site_id"]
        for item in _scan_primary_actions("\n\n" + app_source, shifted_sources)
    ]

    added_sources = dict(ui_sources)
    added_sources["ui/analyst_views.py"] += (
        '\n\ndef ux1b_new_action():\n    st.button("新增動作", type="primary")\n'
    )
    _expect_assertion(
        lambda: _validate_primary_action_ledger(
            classification, app_source, added_sources
        )
    )

    relabeled_sources = dict(ui_sources)
    relabeled_sources["ui/analyst_views.py"] = relabeled_sources[
        "ui/analyst_views.py"
    ].replace('c2.button("查詢", type="primary")', 'c2.button("刪除全部資料", type="primary")', 1)
    _expect_assertion(
        lambda: _validate_primary_action_ledger(
            classification, app_source, relabeled_sources
        )
    )

    dynamic_sources = dict(ui_sources)
    dynamic_sources["ui/analyst_views.py"] = dynamic_sources[
        "ui/analyst_views.py"
    ].replace('c2.button("查詢", type="primary")', 'c2.button("查詢", type=button_type)', 1)
    _expect_inventory_error(
        lambda: _scan_primary_actions(app_source, dynamic_sources), "string literal"
    )
    _expect_inventory_error(
        lambda: _scan_primary_actions(
            app_source + '\ncustom_action("go", type="primary")\n', ui_sources
        ),
        "unsupported",
    )
    _expect_inventory_error(
        lambda: _scan_primary_actions(
            app_source + '\nst.button("go", **{"type": "primary"})\n', ui_sources
        ),
        "**kwargs",
    )

    danger = copy.deepcopy(classification)
    moved = danger["primary_actions"]["ordinary_interaction"].pop(0)
    danger["primary_actions"]["danger_destructive"].append(moved)
    _expect_assertion(
        lambda: _validate_primary_action_ledger(danger, app_source, ui_sources)
    )

    removed = copy.deepcopy(classification)
    removed["primary_actions"]["ordinary_interaction"].pop()
    _expect_assertion(
        lambda: _validate_primary_action_ledger(
            removed, app_source, ui_sources
        )
    )
    occurrence = copy.deepcopy(classification)
    occurrence_id = occurrence["primary_actions"]["ordinary_interaction"][0]
    occurrence["primary_actions"]["ordinary_interaction"][0] = (
        occurrence_id.rsplit("|", 1)[0] + "|2"
    )
    _expect_assertion(
        lambda: _validate_primary_action_ledger(
            occurrence, app_source, ui_sources
        )
    )
    fingerprint = copy.deepcopy(classification)
    fingerprint_id = fingerprint["primary_actions"]["ordinary_interaction"][0]
    fingerprint_parts = fingerprint_id.split("|")
    fingerprint_parts[-2] = "0" * 64
    fingerprint["primary_actions"]["ordinary_interaction"][0] = "|".join(
        fingerprint_parts
    )
    _expect_assertion(
        lambda: _validate_primary_action_ledger(
            fingerprint, app_source, ui_sources
        )
    )


def test_ux1b_prechange_and_forward_mutations_fail_closed() -> None:
    prechange = json.loads(UX1B_PRECHANGE_PATH.read_text(encoding="utf-8"))
    classification = json.loads(UX1B_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    ux1a_contract = json.loads(UX1A_CONTRACT_PATH.read_text(encoding="utf-8"))
    metric_id = next(
        site_id for site_id in ux1a_contract["current_contract"]["unsafe_site_ids"]
        if site_id.startswith("app.py|<module>|st.markdown|constant|")
    )
    normalized = copy.deepcopy(classification)
    normalized["scope"]["protected_parent_metric_site_id"] = metric_id
    current_inventory = inventory.build_inventory(ROOT)
    _validate_ux1b_forward_projection(normalized, current_inventory)
    accepted_without_site = copy.deepcopy(normalized)
    accepted_without_site["state"] = "accepted"
    accepted_without_site["unsafe_html"]["trusted_static_theme_css"] = []
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(
            accepted_without_site, current_inventory
        )
    )

    changed_page = copy.deepcopy(prechange)
    changed_page["frozen_page_projection"]["records"][0]["callable"] = "other.render"
    _expect_assertion(lambda: _validate_ux1b_prechange(changed_page, normalized))
    changed_marker = copy.deepcopy(prechange)
    changed_marker["ready_markers"][0]["text"] = "猜測的 nav title"
    _expect_assertion(lambda: _validate_ux1b_prechange(changed_marker, normalized))
    changed_plan = copy.deepcopy(prechange)
    changed_plan["accepted_plan"]["sha256"] = "0" * 64
    _expect_assertion(lambda: _validate_ux1b_prechange(changed_plan, normalized))
    changed_rollback = copy.deepcopy(prechange)
    changed_rollback["rollback_source"]["manifest_path"] = "../manifest.json"
    _expect_assertion(lambda: _validate_ux1b_rollback(changed_rollback, normalized))

    app_source, ui_sources = _sources()
    added_unsafe = inventory.analyze_sources(
        app_source + '\nst.markdown("<style>.new{color:red}</style>", unsafe_allow_html=True)\n',
        ui_sources,
    )
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(normalized, added_unsafe)
    )
    replaced_metric = inventory.analyze_sources(
        app_source.replace("font-size: 1.5rem", "font-size: 1.6rem", 1),
        ui_sources,
    )
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(normalized, replaced_metric)
    )
    added_diagnostic_sources = dict(ui_sources)
    added_diagnostic_sources["ui/analyst_views.py"] += (
        '\n\ndef ux1b_diagnostic(path):\n    st.code(path)\n'
    )
    added_diagnostic = inventory.analyze_sources(app_source, added_diagnostic_sources)
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(normalized, added_diagnostic)
    )

    removed_diagnostic = copy.deepcopy(current_inventory)
    removed_diagnostic["diagnostics"].pop()
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(
            normalized, removed_diagnostic
        )
    )
    occurrence_diagnostic = copy.deepcopy(current_inventory)
    occurrence_row = next(
        row
        for row in occurrence_diagnostic["diagnostics"]
        if row["site_id"] in CODEX_DIAGNOSTIC_ADDITIONS
    )
    occurrence_row["occurrence"] = 2
    occurrence_row["site_id"] = (
        occurrence_row["site_id"].rsplit("|", 1)[0] + "|2"
    )
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(
            normalized, occurrence_diagnostic
        )
    )
    fingerprint_diagnostic = copy.deepcopy(current_inventory)
    fingerprint_row = next(
        row
        for row in fingerprint_diagnostic["diagnostics"]
        if row["site_id"] in CODEX_DIAGNOSTIC_ADDITIONS
    )
    fingerprint_row["fingerprint"] = "0" * 64
    fingerprint_parts = fingerprint_row["site_id"].split("|")
    fingerprint_parts[-2] = "0" * 64
    fingerprint_row["site_id"] = "|".join(fingerprint_parts)
    _expect_assertion(
        lambda: _validate_ux1b_forward_projection(
            normalized, fingerprint_diagnostic
        )
    )


def test_ux1b_prechange_plan_pages_markers_and_rollback() -> None:
    assert _sha256(UX1B_PRECHANGE_PATH) == UX1B_PRECHANGE_SHA256
    prechange = json.loads(UX1B_PRECHANGE_PATH.read_text(encoding="utf-8"))
    classification = json.loads(UX1B_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    _validate_ux1b_prechange(prechange, classification)
    _validate_ux1b_rollback(prechange, classification)


def test_ux1b_forward_classification_and_backward_projection() -> None:
    assert _sha256(CLASSIFICATION_PATH) == UX1A_CLASSIFICATION_SHA256
    assert _sha256(UX1A_CONTRACT_PATH) == UX1A_CONTRACT_SHA256
    classification = json.loads(UX1B_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    app_source, ui_sources = _sources()
    _validate_primary_action_ledger(classification, app_source, ui_sources)
    _validate_ux1b_forward_projection(classification, inventory.build_inventory(ROOT))


def test_ux1a_classification_and_current_contract() -> None:
    assert _sha256(CLASSIFICATION_PATH) == UX1A_CLASSIFICATION_SHA256
    assert _sha256(UX1A_CONTRACT_PATH) == UX1A_CONTRACT_SHA256
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    classification = json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    contract = json.loads(UX1A_CONTRACT_PATH.read_text(encoding="utf-8"))
    stored_current = contract["current_contract"]

    assert set(classification) == {
        "diagnostics",
        "parent_baseline",
        "rationales",
        "schema_version",
        "scope",
        "summary",
        "unsafe_html",
    }
    assert classification["schema_version"] == (
        "quant-radar-ui-ux-ux1a-classification/v1"
    )
    assert classification["parent_baseline"] == {
        "diagnostic_count": 177,
        "path": "docs/ui-ux/quant-radar-ui-v2-baseline.json",
        "sha256": BASELINE_SHA256,
        "unsafe_count": 31,
    }
    assert classification["scope"] == {
        "diagnostic_scanner_coverage": [
            "st.code",
            "st.json",
            "*.download_button.data",
        ],
        "target_files": sorted(UX1A_INVENTORY_TARGET_FILES),
    }
    assert set(classification["rationales"]["unsafe_html"]) == (
        UNSAFE_CLASSIFICATIONS
    )
    assert set(classification["rationales"]["diagnostics"]) == (
        DIAGNOSTIC_CLASSIFICATIONS
    )
    assert all(
        isinstance(value, str) and value
        for group in classification["rationales"].values()
        for value in group.values()
    )

    unsafe_ids, unsafe_by_site = _flatten_buckets(
        classification["unsafe_html"], UNSAFE_CLASSIFICATIONS
    )
    historical_unsafe = {
        item["site_id"] for item in baseline["contract"]["unsafe_html"]
    }
    current_unsafe = set(stored_current["unsafe_site_ids"])
    assert len(unsafe_ids) == 31
    assert set(unsafe_ids) == historical_unsafe
    inventory.require_classified_unsafe_sites(
        {"unsafe_html": [{"site_id": site_id} for site_id in current_unsafe]},
        unsafe_ids,
    )
    assert not {
        site_id
        for site_id in current_unsafe
        if unsafe_by_site[site_id] == "removed_ux1a"
    }
    assert set(classification["unsafe_html"]["removed_ux1a"]) == (
        historical_unsafe - current_unsafe
    )

    diagnostic_ids, diagnostic_by_site = _flatten_buckets(
        classification["diagnostics"], DIAGNOSTIC_CLASSIFICATIONS
    )
    historical_diagnostics = {
        item["site_id"] for item in baseline["contract"]["diagnostics"]
    }
    current_diagnostics = set(stored_current["diagnostic_site_ids"])
    target_files = set(classification["scope"]["target_files"])
    assert set(diagnostic_ids) == historical_diagnostics | current_diagnostics
    assert set(classification["diagnostics"]["fixed"]) == (
        historical_diagnostics - current_diagnostics
    )
    assert all(
        diagnostic_by_site[site_id] != "fixed" for site_id in current_diagnostics
    )
    historical_by_id = {
        item["site_id"]: item for item in baseline["contract"]["diagnostics"]
    }
    for site_id in historical_diagnostics | current_diagnostics:
        item = historical_by_id.get(site_id)
        relative_file = item["file"] if item else site_id.split("|", 1)[0]
        if relative_file in target_files:
            assert diagnostic_by_site[site_id] in {
                "fixed",
                "safe",
                "false_positive",
            }
        else:
            assert diagnostic_by_site[site_id] == "deferred"

    unsafe_counts = {
        key: len(value) for key, value in classification["unsafe_html"].items()
    }
    diagnostic_counts = {
        key: len(value) for key, value in classification["diagnostics"].items()
    }
    assert classification["summary"] == {
        "diagnostics": {
            "classified_union": len(diagnostic_ids),
            "counts": diagnostic_counts,
            "current": len(current_diagnostics),
            "historical": len(historical_diagnostics),
        },
        "unsafe_html": {
            "counts": unsafe_counts,
            "current": len(current_unsafe),
            "historical": len(historical_unsafe),
        },
    }

    assert set(contract) == {
        "classification",
        "current_contract",
        "deferred_counts",
        "intentional_delta",
        "parent_baseline",
        "schema_version",
    }
    assert contract["schema_version"] == "quant-radar-ui-ux-ux1a-contract/v1"
    assert contract["parent_baseline"] == {
        "canonical_contract_sha256": _canonical_sha256(baseline["contract"]),
        "path": "docs/ui-ux/quant-radar-ui-v2-baseline.json",
        "sha256": BASELINE_SHA256,
    }
    assert contract["classification"] == {
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1a-classification.json",
        "sha256": _sha256(CLASSIFICATION_PATH),
    }

    safety = {
        "diagnostic_site_ids": sorted(current_diagnostics),
        "unsafe_site_ids": sorted(current_unsafe),
    }
    assert set(stored_current) == {
        "canonical_sha256",
        "compatibility_sha256",
        "counts",
        "diagnostic_site_ids",
        "inventory_schema_version",
        "safety_sha256",
        "unsafe_site_ids",
    }
    assert stored_current["inventory_schema_version"] == inventory.SCHEMA_VERSION
    assert stored_current["counts"] == {
        "diagnostics": len(current_diagnostics),
        "unsafe_html": len(current_unsafe),
    }
    assert stored_current["diagnostic_site_ids"] == sorted(current_diagnostics)
    assert stored_current["unsafe_site_ids"] == sorted(current_unsafe)
    assert stored_current["safety_sha256"] == _canonical_sha256(safety)
    assert re.fullmatch(r"[0-9a-f]{64}", stored_current["canonical_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", stored_current["compatibility_sha256"])

    unsafe_removed = sorted(historical_unsafe - current_unsafe)
    unsafe_added = sorted(current_unsafe - historical_unsafe)
    diagnostic_removed = sorted(historical_diagnostics - current_diagnostics)
    diagnostic_added = sorted(current_diagnostics - historical_diagnostics)
    assert contract["intentional_delta"] == {
        "diagnostics": {
            "added_site_ids": diagnostic_added,
            "current_count": len(current_diagnostics),
            "parent_count": len(historical_diagnostics),
            "removed_site_ids": diagnostic_removed,
        },
        "unsafe_html": {
            "added_site_ids": unsafe_added,
            "current_count": len(current_unsafe),
            "parent_count": len(historical_unsafe),
            "removed_site_ids": unsafe_removed,
        },
    }
    assert contract["deferred_counts"] == {
        "diagnostics_current": sum(
            diagnostic_by_site[site_id] == "deferred"
            for site_id in current_diagnostics
        ),
        "diagnostics_historical": sum(
            diagnostic_by_site[site_id] == "deferred"
            for site_id in historical_diagnostics
        ),
        "unsafe_html_current": sum(
            unsafe_by_site[site_id] == "deferred_ux4"
            for site_id in current_unsafe
        ),
    }

    encoded = inventory.canonical_json({
        "classification": classification,
        "contract": contract,
    })
    assert str(ROOT) not in encoded


def test_user_surface_sink_ids_are_deterministic_and_payload_targeted() -> None:
    source = '''
def render(payload):
    st.code(payload, language="text")
    st.json(payload, expanded=False)
    st.download_button("export", data=payload, file_name="result.json")
'''
    first = inventory.scan_ui_source(source, "ui/surface.py")["diagnostics"]
    shifted = inventory.scan_ui_source("\n\n\n" + source, "ui/surface.py")[
        "diagnostics"
    ]
    assert {item["sink"] for item in first} == {
        "st.code",
        "st.download_button.data",
        "st.json",
    }
    assert [item["site_id"] for item in first] == [
        item["site_id"] for item in shifted
    ]
    assert all(
        {"user_surface_payload", "download_payload"} & set(item["categories"])
        for item in first
    )


def test_new_unclassified_unsafe_site_fails_closed() -> None:
    classification = json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    classified_ids, _by_site = _flatten_buckets(
        classification["unsafe_html"], UNSAFE_CLASSIFICATIONS
    )
    synthetic = inventory.scan_ui_source(
        '''
def render():
    st.markdown("<b>new surface</b>", unsafe_allow_html=True)
''',
        "ui/new_surface.py",
    )
    _expect_inventory_error(
        lambda: inventory.require_classified_unsafe_sites(
            synthetic, classified_ids
        ),
        "new unclassified unsafe HTML sites",
    )


def test_diagnostic_scanner_covers_required_categories_and_name_flow() -> None:
    source = '''
from pathlib import Path

def exception_panel():
    try:
        raise RuntimeError("boom")
    except Exception as exc:
        detail = str(exc)
        message = f"failed: {detail}"
        st.error(message)

def payload_panel(profile_name, service_port):
    artifact_path = Path("/tmp/private.json")
    internal_url = "http://127.0.0.1:8123/private"
    secret_token = "sk-secret-sentinel"
    payload = {
        "error": "provider failed",
        "path": artifact_path,
        "url": internal_url,
        "profile": profile_name,
        "port": service_port,
        "token": secret_token,
    }
    st.session_state["diagnostic"] = payload

def process_panel(worker_pid, log_tail):
    st.expander(f"pid={worker_pid} log={log_tail}")
'''
    diagnostics = inventory.scan_ui_source(source, "ui/synthetic.py")["diagnostics"]
    categories = {category for item in diagnostics for category in item["categories"]}
    assert {
        "exception",
        "exception_string",
        "f_string",
        "payload_error",
        "path",
        "url",
        "host",
        "port",
        "profile",
        "secret",
        "pid",
        "log",
    } <= categories
    assert {item["sink"] for item in diagnostics} >= {
        "st.error",
        "session_state.write",
        "st.expander",
    }


def test_diagnostic_taint_is_function_local_and_persistence_is_visible() -> None:
    source = '''
def source_scope():
    secret_token = "sk-secret-sentinel"
    detail = secret_token
    st.warning(detail)

def clean_scope():
    detail = "all good"
    st.info(detail)

def persistence_scope(exc, history, output_path):
    payload = {"error": str(exc)}
    history.append(payload)
    output_path.write_text(str(exc))
'''
    diagnostics = inventory.scan_ui_source(source, "ui/scopes.py")["diagnostics"]
    assert not any(item["function"] == "clean_scope" for item in diagnostics)
    assert not any(item["sink"] == "st.info" for item in diagnostics)
    persistence = {
        item["sink"] for item in diagnostics if item["function"] == "persistence_scope"
    }
    assert {"collection.append", "persistence.write_text"} <= persistence
    encoded = inventory.canonical_json(diagnostics)
    assert "sk-secret-sentinel" not in encoded


def test_malformed_python_fails_with_stable_validation_error() -> None:
    _app_source, ui_sources = _sources()
    _expect_inventory_error(
        lambda: inventory.analyze_sources("nav = {", ui_sources), "app.py"
    )


def test_cli_json_help_version_and_error_channels() -> None:
    command = [sys.executable, str(SCRIPTS / "ui_ux_inventory.py")]
    with tempfile.TemporaryDirectory() as temp_dir:
        json_run = subprocess.run(
            [*command, "--json"],
            cwd=temp_dir,
            text=True,
            capture_output=True,
            check=False,
        )
    assert json_run.returncode == 0, json_run.stderr
    assert json_run.stderr == ""
    parsed = json.loads(json_run.stdout)
    assert json_run.stdout == inventory.canonical_json(parsed) + "\n"

    help_run = subprocess.run(
        [*command, "--help"], text=True, capture_output=True, check=False
    )
    assert help_run.returncode == 0
    assert "--json" in help_run.stdout
    assert "--version" in help_run.stdout
    assert help_run.stderr == ""

    version_run = subprocess.run(
        [*command, "--version"], text=True, capture_output=True, check=False
    )
    assert version_run.returncode == 0
    assert version_run.stdout == f"ui_ux_inventory {inventory.VERSION}\n"
    assert version_run.stderr == ""

    bad_run = subprocess.run(
        [*command, "--not-a-real-option"], text=True, capture_output=True, check=False
    )
    assert bad_run.returncode == 2
    assert bad_run.stdout == ""
    assert "error:" in bad_run.stderr

    original_build_inventory = inventory.build_inventory
    stdout, stderr = io.StringIO(), io.StringIO()

    def fail_inventory() -> dict[str, object]:
        raise inventory.InventoryError("synthetic invalid contract")

    try:
        inventory.build_inventory = fail_inventory
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = inventory.main(["--json"])
    finally:
        inventory.build_inventory = original_build_inventory
    assert return_code == 3
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "error: synthetic invalid contract\n"

    stdout, stderr = io.StringIO(), io.StringIO()

    def crash_inventory() -> dict[str, object]:
        raise RuntimeError("sensitive implementation detail")

    try:
        inventory.build_inventory = crash_inventory
        with redirect_stdout(stdout), redirect_stderr(stderr):
            return_code = inventory.main(["--json"])
    finally:
        inventory.build_inventory = original_build_inventory
    assert return_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "error: unexpected inventory failure (RuntimeError)\n"
    assert "sensitive implementation detail" not in stderr.getvalue()


def main() -> None:
    tests = [
        test_repository_page_and_navigation_contract,
        test_registry_navigation_run_wiring_mutations_fail_closed,
        test_page_and_route_mutations_fail_closed,
        test_same_session_route_forms_and_exact_targets,
        test_handoff_keys_preserve_lifecycle_and_operations,
        test_unsafe_html_semantic_ids_are_unique_and_location_free,
        test_repository_unsafe_inventory_is_deterministic_and_relative,
        test_versioned_baseline_contract_and_evidence_schema,
        test_primary_action_full_call_projection_and_mutations_fail_closed,
        test_ux1b_prechange_and_forward_mutations_fail_closed,
        test_ux1b_prechange_plan_pages_markers_and_rollback,
        test_ux1b_forward_classification_and_backward_projection,
        test_ux1a_classification_and_current_contract,
        test_user_surface_sink_ids_are_deterministic_and_payload_targeted,
        test_new_unclassified_unsafe_site_fails_closed,
        test_diagnostic_scanner_covers_required_categories_and_name_flow,
        test_diagnostic_taint_is_function_local_and_persistence_is_visible,
        test_malformed_python_fails_with_stable_validation_error,
        test_cli_json_help_version_and_error_channels,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
