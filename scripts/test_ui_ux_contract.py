#!/usr/bin/env python3
"""Focused no-pytest contracts for UX-0/UX-1A history and UX-1B forward safety."""

from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import re
import stat
import subprocess
import sys
import tempfile
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ui_ux_inventory as inventory  # noqa: E402
import ui_ux_isolation as isolation  # noqa: E402
import ui_ux_snapshot_matrix as snapshot  # noqa: E402
from ui import _design  # noqa: E402


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
UX1B_HISTORICAL_PLAN_PATH = (
    ROOT / "docs" / "superpowers" / "plans"
    / "2026-07-16-quant-radar-ui-ux-ux1b.md"
)
UX1B_CURRENT_PLAN_PATH = (
    ROOT / "docs" / "superpowers" / "plans"
    / "2026-08-29-quant-radar-ui-ux-ux1b-current-main-superseding.md"
)
UX1B_PRECHANGE_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-prechange.json"
)
UX1B_CLASSIFICATION_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-classification.json"
)
UX1B_PRE_RELEASE_VERIFICATION_RELATIVE = (
    "docs/ui-ux/quant-radar-ui-v2-ux1b-posttheme-verification-2026-09-02.json"
)
UX1B_PRE_RELEASE_VERIFICATION_PATH = ROOT / UX1B_PRE_RELEASE_VERIFICATION_RELATIVE
UX1B_CURRENT_HEAD_RECONCILIATION_RELATIVE = (
    "docs/ui-ux/quant-radar-ui-v2-ux1b-current-head-reconciliation-2026-09-02.json"
)
UX1B_CURRENT_HEAD_RECONCILIATION_PATH = (
    ROOT / UX1B_CURRENT_HEAD_RECONCILIATION_RELATIVE
)
UX1B_RELEASE_CLOSURE_PATTERN = re.compile(
    r"docs/ui-ux/quant-radar-ui-v2-ux1b-release-closure-\d{4}-\d{2}-\d{2}\.json"
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
UX1B_HISTORICAL_PLAN_SHA256 = (
    "48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7"
)
UX1B_CURRENT_PLAN_SHA256 = (
    "e547bd4b5b39fd3c0df4b90480aca9fa7e2088e8958eb6dace2a45a478c1a227"
)
UX1B_PRECHANGE_SHA256 = (
    "38443c1483b03f7bf6bdc5095da161059e7f06e8859d9ba7f1d282413e50d674"
)
UX1B_HISTORICAL_PENDING_CLASSIFICATION_SHA256 = (
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
    assert len(classified) == len(set(classified)) == 20
    assert classified == current_ids


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
    prechange: Mapping[str, object], _current_classification: Mapping[str, object]
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
        "sha256": UX1B_HISTORICAL_PLAN_SHA256,
        "size": UX1B_HISTORICAL_PLAN_PATH.stat().st_size,
    }
    assert _sha256(UX1B_HISTORICAL_PLAN_PATH) == UX1B_HISTORICAL_PLAN_SHA256

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
        "sha256": UX1B_HISTORICAL_PENDING_CLASSIFICATION_SHA256,
        "size": 4316,
        "task0_created": True,
    }

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
    prechange: Mapping[str, object], _current_classification: Mapping[str, object]
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
    assert manifest["accepted_plan"] == {
        "path": prechange["accepted_plan"]["path"],  # type: ignore[index]
        "sha256": prechange["accepted_plan"]["sha256"],  # type: ignore[index]
    }
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


def _trusted_css_delta_ids(classification: Mapping[str, object]) -> set[str]:
    unsafe = classification["unsafe_html"]
    assert isinstance(unsafe, Mapping) and set(unsafe) == {"trusted_static_theme_css"}
    records = unsafe["trusted_static_theme_css"]
    assert isinstance(records, list)
    assert classification["state"] in {"pending", "accepted"}
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


def _load_repo_json_evidence(
    record: object,
    *,
    expected_path: str | None = None,
    path_pattern: re.Pattern[str] | None = None,
) -> Mapping[str, object]:
    assert isinstance(record, Mapping)
    assert set(record) == {"path", "sha256"}
    relative = record["path"]
    digest = record["sha256"]
    assert isinstance(relative, str) and relative
    assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
    pure = PurePosixPath(relative)
    assert not pure.is_absolute()
    assert ".." not in pure.parts
    assert str(pure) == relative
    if expected_path is not None:
        assert relative == expected_path
    if path_pattern is not None:
        assert path_pattern.fullmatch(relative)
    path = ROOT / relative
    assert path.is_file() and not path.is_symlink()
    assert ROOT.resolve() in path.resolve().parents
    assert _sha256(path) == digest
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, Mapping)
    return value


def _assert_nonzero_sha256(value: object) -> None:
    assert isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
    assert value != "0" * 64


def _assert_git_commit(value: object) -> None:
    assert isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)
    assert value != "0" * 40


def _assert_nonnegative_int(value: object) -> None:
    assert isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _assert_positive_int(value: object) -> None:
    _assert_nonnegative_int(value)
    assert value > 0  # type: ignore[operator]


def _validate_private_manifest_path(value: object, prefix: str) -> None:
    assert isinstance(value, str)
    pure = PurePosixPath(value)
    assert not pure.is_absolute() and ".." not in pure.parts
    assert str(pure) == value
    assert pure.parts[:3] == (".claude", "ui_snapshots", "ux1b")
    assert len(pure.parts) == 5
    assert pure.parts[3].startswith(prefix + "-")
    assert pure.name == "manifest.json"


def _load_private_manifest(
    record: Mapping[str, object], prefix: str
) -> tuple[Mapping[str, object], Path]:
    """Load one private manifest only when its receipt binds the exact bytes."""

    relative = record["manifest"]
    _validate_private_manifest_path(relative, prefix)
    assert isinstance(relative, str)
    path = ROOT / relative
    observed = path.lstat()
    assert stat.S_ISREG(observed.st_mode) and not path.is_symlink()
    assert ROOT.resolve() in path.resolve(strict=True).parents
    assert record["manifest_sha256"] == _sha256(path)
    assert record["manifest_size"] == observed.st_size
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, Mapping)
    assert payload.get("schemaVersion") == "quant-radar-ui-ux-evidence/v1"
    return payload, path


def _private_artifact_inventory(run_directory: Path) -> Mapping[str, int]:
    counts = {
        "file_count": 0,
        "json_count": 0,
        "non_0600_file_count": 0,
        "png_count": 0,
        "symlink_count": 0,
    }
    for path in run_directory.rglob("*"):
        observed = path.lstat()
        if stat.S_ISLNK(observed.st_mode):
            counts["symlink_count"] += 1
            continue
        if not stat.S_ISREG(observed.st_mode):
            continue
        counts["file_count"] += 1
        counts["json_count"] += path.suffix == ".json"
        counts["png_count"] += path.suffix == ".png"
        counts["non_0600_file_count"] += stat.S_IMODE(observed.st_mode) != 0o600
    return counts


def _validate_full_or_manifest_only_inventory(
    observed: Mapping[str, int], expected_full: Mapping[str, int]
) -> bool:
    """Accept a full private run or its exact Git-distributed manifest projection."""

    if observed["file_count"] == 1:
        assert observed["json_count"] == 1
        assert observed["png_count"] == 0
        assert observed["symlink_count"] == 0
        # Git preserves the file, not its private runtime mode; local evidence is
        # 0600 while a clean checkout is normally 0644.
        assert observed["non_0600_file_count"] in {0, 1}
        return False
    assert observed == expected_full
    return True


def _formal_source_mirror_digest() -> str:
    """Recompute the strict mirror projection without trusting the receipt."""

    assert snapshot.WORKSPACE_ROOT.resolve() == ROOT.resolve()
    records: list[dict[str, object]] = []
    for relative in snapshot._expanded_ux1b_source_mirror_policy():
        path = ROOT / relative
        observed = path.lstat()
        assert stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1
        raw = path.read_bytes()
        after = path.lstat()
        assert (
            observed.st_dev,
            observed.st_ino,
            observed.st_size,
            observed.st_mtime_ns,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
                "mode": "0555" if observed.st_mode & 0o111 else "0444",
            }
        )
    payload = {"schemaVersion": isolation.MIRROR_SCHEMA, "files": records}
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _validate_ux1b_pre_release_receipt(receipt: Mapping[str, object]) -> None:
    assert set(receipt) == {
        "accepted_plan",
        "artifacts",
        "capture_stack",
        "classification_state",
        "current_head_reconciliation",
        "dependency_compatibility",
        "failed_attempts_retained",
        "focused_verification",
        "generated_at_local",
        "generated_at_utc",
        "limitations",
        "non_interference",
        "production_batch",
        "release_gates",
        "rollback_rehearsal",
        "schema_version",
        "security_scan",
        "source_transactions",
        "status",
        "technical_gate_status",
        "test_infrastructure_batch",
        "verification",
    }
    assert receipt["schema_version"] == (
        "quant-radar-ui-ux-ux1b-posttheme-verification/v1"
    )
    # This is a pre-release evidence receipt, not a lifecycle acceptance record.
    # Technical completion is carried only by technical_gate_status.
    assert receipt["status"] == "pending"
    assert receipt["classification_state"] == "pending"
    technical_status = receipt["technical_gate_status"]
    assert technical_status in {"PENDING_REVERIFY", "PASS"}
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        str(receipt["generated_at_utc"]),
    )
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}",
        str(receipt["generated_at_local"]),
    )
    assert receipt["accepted_plan"] == {
        "path": UX1B_CURRENT_PLAN_PATH.relative_to(ROOT).as_posix(),
        "sha256": UX1B_CURRENT_PLAN_SHA256,
        "size": UX1B_CURRENT_PLAN_PATH.stat().st_size,
    }
    reconciliation_record = receipt["current_head_reconciliation"]
    assert isinstance(reconciliation_record, Mapping)
    _load_repo_json_evidence(
        reconciliation_record,
        expected_path=UX1B_CURRENT_HEAD_RECONCILIATION_RELATIVE,
    )

    artifacts = receipt["artifacts"]
    assert isinstance(artifacts, Mapping)
    assert set(artifacts) == {"final_posttheme", "pretheme", "theme_gallery"}
    final_posttheme = artifacts["final_posttheme"]
    assert isinstance(final_posttheme, Mapping)
    assert set(final_posttheme) == {
        "file_count",
        "json_count",
        "manifest",
        "manifest_sha256",
        "manifest_size",
        "non_0600_file_count",
        "png_count",
        "symlink_count",
    }
    final_manifest, final_manifest_path = _load_private_manifest(
        final_posttheme, "posttheme"
    )
    assert final_manifest["status"] == "passed"
    assert final_manifest["phase"] == "posttheme"
    assert final_manifest["mode"] == "ux1b-full-pages"
    assert final_manifest["capturedCount"] == 81
    assert final_manifest["expectedCaptureCount"] == 81
    assert isinstance(final_manifest["captures"], list)
    assert len(final_manifest["captures"]) == 81
    assert final_posttheme["file_count"] == 163
    assert final_posttheme["json_count"] == 82
    assert final_posttheme["png_count"] == 81
    assert final_posttheme["non_0600_file_count"] == 0
    assert final_posttheme["symlink_count"] == 0
    final_inventory = _private_artifact_inventory(final_manifest_path.parent)
    final_artifacts_available = _validate_full_or_manifest_only_inventory(
        final_inventory,
        {
            key: final_posttheme[key]
            for key in (
                "file_count",
                "json_count",
                "non_0600_file_count",
                "png_count",
                "symlink_count",
            )
        },
    )

    pretheme = artifacts["pretheme"]
    assert isinstance(pretheme, Mapping)
    assert set(pretheme) == {"manifest", "manifest_sha256", "manifest_size"}
    pretheme_manifest, _pretheme_manifest_path = _load_private_manifest(
        pretheme, "pretheme"
    )
    assert pretheme_manifest["status"] == "passed"
    assert pretheme_manifest["phase"] == "pretheme"
    assert pretheme_manifest["mode"] == "ux1b-full-pages"
    assert pretheme_manifest["capturedCount"] == 81
    assert pretheme_manifest["expectedCaptureCount"] == 81

    theme_gallery = artifacts["theme_gallery"]
    assert isinstance(theme_gallery, Mapping)
    assert set(theme_gallery) == {
        "capture_count",
        "manifest",
        "manifest_sha256",
        "manifest_size",
        "surface_crop_count",
    }
    theme_manifest, theme_manifest_path = _load_private_manifest(
        theme_gallery, "theme-states"
    )
    assert theme_manifest["status"] == "passed"
    assert theme_manifest["phase"] == "posttheme"
    assert theme_manifest["mode"] == "ux1b-theme"
    assert theme_manifest["capturedCount"] == 3
    assert theme_manifest["expectedCaptureCount"] == 3
    assert theme_manifest["summary"] == {"failed": 0, "passed": 3, "total": 3}
    assert theme_manifest["supplementalArtifactCount"] == 9
    assert theme_gallery["capture_count"] == 3
    assert theme_gallery["surface_crop_count"] == 9
    theme_inventory = _private_artifact_inventory(theme_manifest_path.parent)
    theme_artifacts_available = _validate_full_or_manifest_only_inventory(
        theme_inventory,
        {
            "file_count": 16,
            "json_count": 4,
            "non_0600_file_count": 0,
            "png_count": 12,
            "symlink_count": 0,
        },
    )

    capture_stack = receipt["capture_stack"]
    assert isinstance(capture_stack, Mapping)
    assert set(capture_stack) == {
        "capture_stack_digest",
        "path",
        "sha256",
        "size",
    }
    capture_stack_path = ROOT / "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json"
    assert capture_stack["path"] == capture_stack_path.relative_to(ROOT).as_posix()
    assert capture_stack["sha256"] == _sha256(capture_stack_path)
    assert capture_stack["size"] == capture_stack_path.stat().st_size
    _assert_nonzero_sha256(capture_stack["capture_stack_digest"])
    capture_stack_payload = json.loads(capture_stack_path.read_text(encoding="utf-8"))
    assert capture_stack["capture_stack_digest"] == capture_stack_payload[
        "captureStackDigest"
    ]
    capture_stack_digest = capture_stack["capture_stack_digest"]
    assert final_manifest["captureStackDigest"] == capture_stack_digest
    assert pretheme_manifest["captureStackDigest"] == capture_stack_digest
    assert theme_manifest["captureStackDigest"] == capture_stack_digest

    limitations = receipt["limitations"]
    assert isinstance(limitations, Mapping)
    assert set(limitations) == {
        "participant_sus_seq_study",
        "safari",
        "ux2_shell",
    }
    assert limitations["safari"] == "unverified"
    assert limitations["participant_sus_seq_study"] == "unverified"
    assert isinstance(limitations["ux2_shell"], str) and limitations["ux2_shell"]
    non_interference = receipt["non_interference"]
    assert isinstance(non_interference, Mapping)
    assert set(non_interference) == {
        "api_or_database_schema_changed",
        "data_report_pick_ledger_score_weight_threshold_or_schedule_changed",
        "dependencies_changed",
        "provider_or_network_behavior_changed",
        "seven_f_state_changed",
        "source_capture_prohibited_counters",
    }
    for key in (
        "api_or_database_schema_changed",
        "data_report_pick_ledger_score_weight_threshold_or_schedule_changed",
        "provider_or_network_behavior_changed",
        "seven_f_state_changed",
    ):
        assert non_interference[key] is False
    assert non_interference["dependencies_changed"] is True
    dependency = receipt["dependency_compatibility"]
    assert dependency == {
        "declared_after": "streamlit==1.57.0",
        "declared_before": "streamlit>=1.40.0",
        "installed_verification_version": "1.57.0",
        "compatibility_probe": {
            "1.47.0": {
                "keyed_link_button": False,
                "linkColor": True,
                "linkUnderline": True,
                "verified_theme_dom": False,
            },
            "1.57.0": {
                "keyed_link_button": True,
                "linkColor": True,
                "linkUnderline": True,
                "verified_theme_dom": True,
            },
        },
        "reason": (
            "The formal browser evidence, keyed link-button fixture, and "
            "component-scoped DOM selectors were verified together on 1.57.0; "
            "the former 1.47 floor cannot execute the fixture or reproduce the "
            "verified slider DOM."
        ),
    }
    prohibited = non_interference["source_capture_prohibited_counters"]
    assert prohibited == {
        "network.outbound": 0,
        "production.read": 0,
        "production.write": 0,
    }
    failed_attempts = receipt["failed_attempts_retained"]
    assert isinstance(failed_attempts, list) and failed_attempts
    failed_manifests: set[str] = set()
    required_failed_keys = {
        "diagnostic",
        "manifest",
        "manifest_sha256",
        "manifest_size",
        "status",
    }
    allowed_failed_keys = required_failed_keys | {
        "artifact_file_count",
        "disposition",
        "partial_artifact_count",
    }
    for failed in failed_attempts:
        assert isinstance(failed, Mapping)
        assert required_failed_keys <= set(failed) <= allowed_failed_keys
        failed_manifest, _failed_manifest_path = _load_private_manifest(
            failed,
            (
                "theme-states"
                if "theme-states-" in str(failed["manifest"])
                else "posttheme"
            ),
        )
        assert failed["manifest"] not in failed_manifests
        failed_manifests.add(str(failed["manifest"]))
        assert failed["status"] in {"failed", "invalid_data"}
        assert isinstance(failed["diagnostic"], str) and failed["diagnostic"]
        assert failed_manifest["status"] == failed["status"]
        assert failed_manifest["phase"] == "posttheme"
        error = failed_manifest["error"]
        assert isinstance(error, Mapping)
        assert error["message"] == failed["diagnostic"]
        if "disposition" in failed:
            assert isinstance(failed["disposition"], str) and failed["disposition"]
        for count_key in ("artifact_file_count", "partial_artifact_count"):
            if count_key in failed:
                _assert_positive_int(failed[count_key])

    gates = receipt["release_gates"]
    assert isinstance(gates, Mapping)
    assert set(gates) == {
        "classification_acceptance",
        "full_repository_test",
        "pull_request",
        "seven_f_smoke",
        "test_server_deployment",
        "ux2",
    }
    assert gates["classification_acceptance"] == "pending"
    assert gates["pull_request"] == "pending"
    assert gates["seven_f_smoke"] == "pending"
    assert gates["test_server_deployment"] == "pending"
    assert gates["ux2"] == "unstarted"
    assert gates["full_repository_test"] == (
        "pending reverify"
        if technical_status == "PENDING_REVERIFY"
        else "make test PASS (exit 0)"
    )
    verification = receipt["verification"]
    assert isinstance(verification, Mapping)
    assert set(verification) == {
        "children_quiescent",
        "final_posttheme",
        "manifest_verifier",
        "mutator_counters",
        "pretheme",
        "pretheme_comparison",
        "processes",
        "provider_counters",
        "theme_gallery",
        "visual_review",
    }
    assert verification["final_posttheme"] == "81/81 PASS"
    assert verification["manifest_verifier"] == "PASS"
    assert verification["pretheme"] == "81/81 PASS"
    assert verification["theme_gallery"] == (
        "3/3 captures and 9/9 surface crops PASS"
    )
    assert verification["children_quiescent"] is True
    assert verification["mutator_counters"] == (
        "actual equals expected; all values are zero"
    )
    assert verification["provider_counters"] == "actual equals expected"
    comparison = verification["pretheme_comparison"]
    assert isinstance(comparison, Mapping)
    assert set(comparison) == {
        "canonical_non_color_pair_count",
        "canonical_non_color_projection_sha256",
        "changed_png_count",
        "compared_capture_count",
        "status",
        "unchanged_png_count",
    }
    assert comparison["status"] == "passed"
    assert comparison["canonical_non_color_pair_count"] == 81
    assert comparison["compared_capture_count"] == 81
    _assert_nonzero_sha256(comparison["canonical_non_color_projection_sha256"])
    _assert_nonnegative_int(comparison["changed_png_count"])
    _assert_nonnegative_int(comparison["unchanged_png_count"])
    assert comparison["changed_png_count"] + comparison["unchanged_png_count"] == 81
    manifest_comparison = final_manifest["prethemeComparison"]
    assert isinstance(manifest_comparison, Mapping)
    assert manifest_comparison == {
        "canonicalNonColorPairCount": comparison[
            "canonical_non_color_pair_count"
        ],
        "canonicalNonColorProjectionSha256": comparison[
            "canonical_non_color_projection_sha256"
        ],
        "changedPngCount": comparison["changed_png_count"],
        "comparedCaptureCount": comparison["compared_capture_count"],
        "prethemeManifest": pretheme["manifest"],
        "prethemeManifestSha256": pretheme["manifest_sha256"],
        "status": comparison["status"],
        "themeContract": "docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json",
        "unchangedPngCount": comparison["unchanged_png_count"],
    }
    processes = verification["processes"]
    assert processes == {
        "app_return_code": 0,
        "browser_count": 81,
        "browser_return_codes_zero": True,
        "browser_workers_quiescent": True,
    }
    visual = verification["visual_review"]
    assert isinstance(visual, Mapping)
    assert set(visual) == {
        "final_images_reviewed",
        "images_byte_identical_to_prior_reviewed_pass",
        "images_re_reviewed_at_original_resolution",
        "state_surface_crops_reviewed",
        "status",
    }
    assert visual["status"] == "PASS"
    assert visual["final_images_reviewed"] == 81
    _assert_nonnegative_int(visual["images_byte_identical_to_prior_reviewed_pass"])
    _assert_nonnegative_int(visual["images_re_reviewed_at_original_resolution"])
    assert (
        visual["images_byte_identical_to_prior_reviewed_pass"]
        + visual["images_re_reviewed_at_original_resolution"]
        == 81
    )
    assert visual["state_surface_crops_reviewed"] == 9
    focused = receipt["focused_verification"]
    assert focused == {
        "contract": "21/21 PASS",
        "fixtures": "29/29 PASS",
        "navigation": "66/66 PASS",
        "primary_action_states": "33/33 state targets PASS",
        "snapshot_runner": "64/64 PASS",
        "theme": "12/12 PASS",
        "theme_matrix": "30/30 PASS",
    }
    production = receipt["production_batch"]
    assert isinstance(production, Mapping)
    assert set(production) == {"base_commit", "files", "scope"}
    _assert_git_commit(production["base_commit"])
    assert isinstance(production["scope"], str) and production["scope"]
    files = production["files"]
    assert isinstance(files, Mapping)
    assert set(files) == {
        ".streamlit/config.toml",
        "app.py",
        "requirements.txt",
        "ui/_design.py",
    }
    production_matches_current: list[bool] = []
    for relative, record in files.items():
        assert isinstance(record, Mapping)
        assert set(record) == {"pretheme_sha256", "sha256", "size"}
        _assert_nonzero_sha256(record["pretheme_sha256"])
        _assert_nonzero_sha256(record["sha256"])
        _assert_positive_int(record["size"])
        production_matches_current.append(
            record["sha256"] == _sha256(ROOT / relative)
            and record["size"] == (ROOT / relative).stat().st_size
        )
    assert all(production_matches_current) is (technical_status == "PASS")

    test_infrastructure = receipt["test_infrastructure_batch"]
    assert isinstance(test_infrastructure, Mapping)
    assert set(test_infrastructure) == {
        "files",
        "local_runtime_path",
        "local_runtime_path_kind",
        "production_rollback_excluded",
        "reason",
        "scope",
    }
    assert test_infrastructure["scope"] == "test-infrastructure only"
    assert test_infrastructure["local_runtime_path"] == ".venv"
    assert test_infrastructure["local_runtime_path_kind"] == (
        "runtime-only symlink to the shared virtual environment"
    )
    assert test_infrastructure["production_rollback_excluded"] is True
    assert isinstance(test_infrastructure["reason"], str) and test_infrastructure["reason"]
    infrastructure_files = test_infrastructure["files"]
    assert isinstance(infrastructure_files, Mapping)
    assert set(infrastructure_files) == {
        ".gitignore",
        "scripts/test_ui_reversal_snapshots_api.py",
    }
    for relative, record in infrastructure_files.items():
        assert isinstance(record, Mapping)
        assert set(record) == {"prechange_sha256", "sha256", "size"}
        _assert_nonzero_sha256(record["prechange_sha256"])
        assert record["sha256"] == _sha256(ROOT / relative)
        assert record["size"] == (ROOT / relative).stat().st_size
        assert record["sha256"] != record["prechange_sha256"]

    rehearsal = receipt["rollback_rehearsal"]
    assert isinstance(rehearsal, Mapping)
    assert set(rehearsal) == {
        "base_commit",
        "builder_css_sha256",
        "exact_pretheme_restore",
        "exact_theme_reapply",
        "isolated_detached_worktree",
        "production_files",
        "restore_source",
        "temporary_worktree_removed_cleanly",
    }
    _assert_git_commit(rehearsal["base_commit"])
    assert rehearsal["base_commit"] == production["base_commit"]
    _assert_nonzero_sha256(rehearsal["builder_css_sha256"])
    current_builder_sha256 = hashlib.sha256(
        _design.build_global_theme_css().encode("utf-8")
    ).hexdigest()
    if technical_status == "PENDING_REVERIFY":
        assert rehearsal["builder_css_sha256"] == (
            "da5d96cb562f70713ec3aa913b6a689ecaff674e5d38c6d714e0008ed5d49ce0"
        )
    assert (rehearsal["builder_css_sha256"] == current_builder_sha256) is (
        technical_status == "PASS"
    )
    for key in (
        "exact_pretheme_restore",
        "exact_theme_reapply",
        "isolated_detached_worktree",
        "temporary_worktree_removed_cleanly",
    ):
        assert rehearsal[key] is True
    assert rehearsal["production_files"] == [
        ".streamlit/config.toml",
        "app.py",
        "requirements.txt",
        "ui/_design.py",
    ]
    assert rehearsal["restore_source"] == (
        "Git objects at production_batch.base_commit; the historical "
        "rollback-source bundle was not used"
    )

    security = receipt["security_scan"]
    assert isinstance(security, Mapping)
    assert set(security) == {
        "absolute_host_path_files",
        "artifact_file_count",
        "artifact_json_count",
        "artifact_non_0600_file_count",
        "artifact_png_count",
        "artifact_sensitive_pattern_files",
        "artifact_symlink_count",
        "diff_sensitive_pattern_lines",
    }
    assert security["artifact_file_count"] == 179
    assert security["artifact_json_count"] == 86
    assert security["artifact_png_count"] == 93
    if final_artifacts_available and theme_artifacts_available:
        assert security["artifact_file_count"] == (
            final_inventory["file_count"] + theme_inventory["file_count"]
        )
        assert security["artifact_json_count"] == (
            final_inventory["json_count"] + theme_inventory["json_count"]
        )
        assert security["artifact_png_count"] == (
            final_inventory["png_count"] + theme_inventory["png_count"]
        )
    for zero_key in (
        "absolute_host_path_files",
        "artifact_non_0600_file_count",
        "artifact_symlink_count",
        "diff_sensitive_pattern_lines",
    ):
        assert security[zero_key] == 0
    assert security["artifact_sensitive_pattern_files"] == {
        "aws_access_key": 0,
        "bearer_value": 0,
        "github_token": 0,
        "openai_style_token": 0,
        "pem_private_key": 0,
    }

    source = receipt["source_transactions"]
    assert isinstance(source, Mapping)
    assert set(source) == {
        "formal_mirror",
        "legacy_compatibility_projection",
        "projection_note",
    }
    formal = source["formal_mirror"]
    assert isinstance(formal, Mapping)
    assert set(formal) == {"digest_end", "digest_start", "projection", "stable"}
    assert formal["stable"] is True
    assert formal["digest_start"] == formal["digest_end"]
    _assert_nonzero_sha256(formal["digest_start"])
    current_formal_digest = _formal_source_mirror_digest()
    assert (formal["digest_start"] == current_formal_digest) is (
        technical_status == "PASS"
    )
    assert final_manifest["sourceDigestStart"] == formal["digest_start"]
    assert final_manifest["sourceDigestEnd"] == formal["digest_end"]
    assert theme_manifest["sourceDigestStart"] == formal["digest_start"]
    assert theme_manifest["sourceDigestEnd"] == formal["digest_end"]
    assert formal["projection"] == "formal isolated source mirror"
    legacy = source["legacy_compatibility_projection"]
    assert isinstance(legacy, Mapping)
    assert set(legacy) == {"digest", "projection"}
    _assert_nonzero_sha256(legacy["digest"])
    if technical_status == "PENDING_REVERIFY":
        assert legacy["digest"] == (
            "991647d2b37f65dc7230ff8d987b23878ab39eada340f520352b5a69006b8be9"
        )
    assert (
        legacy["digest"] == snapshot.ux1b_source_digest(root=ROOT)
    ) is (technical_status == "PASS")
    assert legacy["projection"] == "ux1b_source_digest compatibility helper"
    assert source["projection_note"] == (
        "The formal mirror and legacy compatibility helper intentionally cover "
        "different accepted file sets and therefore must not be compared as equal digests."
    )


def _validate_hash_pair(record: object) -> None:
    assert isinstance(record, Mapping)
    assert set(record) == {"after_sha256", "before_sha256", "unchanged"}
    assert re.fullmatch(r"[0-9a-f]{64}", str(record["before_sha256"]))
    assert record["after_sha256"] == record["before_sha256"]
    assert record["unchanged"] is True


def _validate_ux1b_release_closure(
    closure: Mapping[str, object], pre_release_record: Mapping[str, object]
) -> None:
    assert set(closure) == {
        "deployment",
        "limitations",
        "pre_release_verification",
        "pull_request",
        "recorded_at_utc",
        "schema_version",
        "seven_f",
        "status",
        "ux2",
    }
    assert closure["schema_version"] == (
        "quant-radar-ui-ux-ux1b-release-closure/v1"
    )
    assert closure["status"] == "ACCEPTED"
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        str(closure["recorded_at_utc"]),
    )
    assert closure["pre_release_verification"] == dict(pre_release_record)
    pull_request = closure["pull_request"]
    assert isinstance(pull_request, Mapping)
    assert set(pull_request) == {"merge_commit", "merged", "number", "url"}
    assert isinstance(pull_request["number"], int) and pull_request["number"] > 0
    assert pull_request["merged"] is True
    assert pull_request["url"] == (
        "https://github.com/KennyHsiao/surge-screener/pull/"
        f"{pull_request['number']}"
    )
    merge_commit = str(pull_request["merge_commit"])
    assert re.fullmatch(r"[0-9a-f]{40}", merge_commit)
    deployment = closure["deployment"]
    assert isinstance(deployment, Mapping)
    assert set(deployment) == {"deployed_commit", "run_id", "status", "url"}
    assert isinstance(deployment["run_id"], int) and deployment["run_id"] > 0
    assert deployment["status"] == "success"
    assert deployment["deployed_commit"] == merge_commit
    assert deployment["url"] == (
        "https://github.com/KennyHsiao/surge-screener/actions/runs/"
        f"{deployment['run_id']}"
    )
    seven_f = closure["seven_f"]
    assert isinstance(seven_f, Mapping)
    assert set(seven_f) == {
        "analytics_counts",
        "api_http_status",
        "checks",
        "deployed_commit",
        "deployment_files_match",
        "generation",
        "services_active",
        "shared_analytics_db",
        "streamlit_http_status",
        "timers_active",
        "verified_at_utc",
    }
    assert seven_f["deployed_commit"] == merge_commit
    assert seven_f["api_http_status"] == 200
    assert seven_f["streamlit_http_status"] == 200
    assert seven_f["deployment_files_match"] is True
    assert seven_f["services_active"] is True
    assert seven_f["timers_active"] is True
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        str(seven_f["verified_at_utc"]),
    )
    _validate_hash_pair(seven_f["shared_analytics_db"])
    _validate_hash_pair(seven_f["checks"])
    generation = seven_f["generation"]
    assert isinstance(generation, Mapping)
    assert set(generation) == {"after", "before", "unchanged"}
    assert isinstance(generation["before"], str) and generation["before"]
    assert generation["after"] == generation["before"]
    assert generation["unchanged"] is True
    counts = seven_f["analytics_counts"]
    assert isinstance(counts, Mapping)
    assert set(counts) == {"block", "pass", "warn"}
    assert all(
        isinstance(counts[key], int) and not isinstance(counts[key], bool)
        and counts[key] >= 0
        for key in counts
    )
    assert counts["block"] == 0
    assert closure["limitations"] == {
        "participant_sus_seq_study": "unverified",
        "safari": "unverified",
    }
    assert closure["ux2"] == "unstarted"


def _validate_ux1b_current_head_reconciliation(
    reconciliation: Mapping[str, object], receipt: Mapping[str, object]
) -> None:
    assert set(reconciliation) == {
        "accepted_plan",
        "decision",
        "merge",
        "production_files",
        "recorded_at_utc",
        "schema_version",
        "scope",
        "source_binding",
        "status",
    }
    assert reconciliation["schema_version"] == (
        "quant-radar-ui-ux-ux1b-current-head-reconciliation/v1"
    )
    reconciliation_status = reconciliation["status"]
    assert reconciliation_status in {"PENDING_REVERIFY", "PASS"}
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        str(reconciliation["recorded_at_utc"]),
    )
    assert reconciliation["accepted_plan"] == receipt["accepted_plan"]

    merge = reconciliation["merge"]
    assert isinstance(merge, Mapping)
    assert set(merge) == {
        "feature_parent",
        "merge_commit",
        "origin_main_parent",
    }
    for key in ("feature_parent", "merge_commit", "origin_main_parent"):
        _assert_git_commit(merge[key])
    assert len(set(merge.values())) == 3

    scope = reconciliation["scope"]
    assert isinstance(scope, Mapping)
    assert set(scope) == {
        "changed_file_count",
        "changed_paths_sha256",
        "classification",
        "formal_source_projection_files_changed",
        "non_report_or_runtime_data_files",
        "production_files_changed",
    }
    _assert_positive_int(scope["changed_file_count"])
    _assert_nonzero_sha256(scope["changed_paths_sha256"])
    assert scope["classification"] == "report-and-runtime-data-only"
    assert scope["formal_source_projection_files_changed"] == []
    assert scope["production_files_changed"] == []
    assert scope["non_report_or_runtime_data_files"] == []

    source_binding = reconciliation["source_binding"]
    assert isinstance(source_binding, Mapping)
    assert set(source_binding) == {
        "final_capture_formal_digest",
        "formal_recapture_completed_after_guardrail_fixes",
        "formal_recapture_required_after_guardrail_fixes",
        "post_merge_formal_digest_before_guardrail_fixes",
        "pre_merge_receipt_formal_digest",
        "unchanged_by_main_merge",
    }
    for key in (
        "post_merge_formal_digest_before_guardrail_fixes",
        "pre_merge_receipt_formal_digest",
    ):
        _assert_nonzero_sha256(source_binding[key])
    assert source_binding["post_merge_formal_digest_before_guardrail_fixes"] == (
        source_binding["pre_merge_receipt_formal_digest"]
    )
    assert source_binding["unchanged_by_main_merge"] is True
    assert source_binding["formal_recapture_required_after_guardrail_fixes"] is True
    assert source_binding[
        "formal_recapture_completed_after_guardrail_fixes"
    ] is True
    _assert_nonzero_sha256(source_binding["final_capture_formal_digest"])
    if reconciliation_status == "PASS":
        assert receipt["technical_gate_status"] == "PASS"
        formal = receipt["source_transactions"]["formal_mirror"]  # type: ignore[index]
        assert source_binding["final_capture_formal_digest"] == formal["digest_start"]
        assert source_binding["final_capture_formal_digest"] == formal["digest_end"]
        expected_decision = (
            "The post-receipt main merge changed only report/runtime-data paths, left "
            "the formal source projection and production batch unchanged, and does "
            "not invalidate the recaptured final evidence."
        )
    else:
        assert receipt["technical_gate_status"] == "PENDING_REVERIFY"
        expected_decision = (
            "The post-receipt UX-1B release-blocker fixes changed the formal source "
            "projection after the accepted capture; that evidence remains historical "
            "and a fresh formal capture is required before release."
        )

    reconciled_production = reconciliation["production_files"]
    assert isinstance(reconciled_production, Mapping)
    assert set(reconciled_production) == {
        ".streamlit/config.toml",
        "app.py",
        "requirements.txt",
        "ui/_design.py",
    }
    reconciled_matches_current: list[bool] = []
    for relative, record in reconciled_production.items():
        assert isinstance(record, Mapping)
        assert set(record) == {"after_sha256", "before_sha256", "unchanged"}
        _assert_nonzero_sha256(record["before_sha256"])
        assert record["after_sha256"] == record["before_sha256"]
        assert record["unchanged"] is True
        reconciled_matches_current.append(
            record["after_sha256"] == _sha256(ROOT / relative)
        )
    assert all(reconciled_matches_current) is (reconciliation_status == "PASS")

    assert reconciliation["decision"] == expected_decision


def _validate_ux1b_release_evidence(classification: Mapping[str, object]) -> None:
    release = classification["release_evidence"]
    assert isinstance(release, Mapping)
    assert set(release) == {
        "current_head_reconciliation",
        "pre_release_verification",
        "release_closure",
    }
    reconciliation_record = release["current_head_reconciliation"]
    reconciliation = _load_repo_json_evidence(
        reconciliation_record,
        expected_path=UX1B_CURRENT_HEAD_RECONCILIATION_RELATIVE,
    )
    pre_release_record = release["pre_release_verification"]
    receipt = _load_repo_json_evidence(
        pre_release_record,
        expected_path=UX1B_PRE_RELEASE_VERIFICATION_RELATIVE,
    )
    _validate_ux1b_pre_release_receipt(receipt)
    assert receipt["current_head_reconciliation"] == reconciliation_record
    _validate_ux1b_current_head_reconciliation(reconciliation, receipt)
    if classification["state"] == "pending":
        assert release["release_closure"] is None
        return
    assert classification["state"] == "accepted"
    assert release["release_closure"] is not None
    assert receipt["technical_gate_status"] == "PASS"
    closure = _load_repo_json_evidence(
        release["release_closure"],
        path_pattern=UX1B_RELEASE_CLOSURE_PATTERN,
    )
    assert isinstance(pre_release_record, Mapping)
    _validate_ux1b_release_closure(closure, pre_release_record)


def _validate_ux1b_forward_projection(
    classification: Mapping[str, object], current_inventory: Mapping[str, object]
) -> None:
    assert set(classification) == {
        "accepted_plan",
        "parent",
        "primary_actions",
        "rationales",
        "release_evidence",
        "schema_version",
        "scope",
        "state",
        "unsafe_html",
    }
    assert classification["schema_version"] == (
        "quant-radar-ui-ux-ux1b-classification/v1"
    )
    assert classification["state"] in {"pending", "accepted"}
    _validate_ux1b_release_evidence(classification)
    assert classification["accepted_plan"] == {
        "path": (
            "docs/superpowers/plans/"
            "2026-08-29-quant-radar-ui-ux-ux1b-current-main-superseding.md"
        ),
        "sha256": UX1B_CURRENT_PLAN_SHA256,
    }
    assert _sha256(UX1B_CURRENT_PLAN_PATH) == UX1B_CURRENT_PLAN_SHA256
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
        "call_kind": "st.html",
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
    trusted_record = classification["unsafe_html"]["trusted_static_theme_css"][0]
    current_by_id = {item["site_id"]: item for item in current["unsafe_html"]}
    site = current_by_id[trusted_record["site_id"]]
    assert site["file"] == "app.py"
    assert site["function"] == "<module>"
    assert site["call_kind"] == "st.html"
    assert site["expression_category"] == "call"
    assert site["static"] is False
    assert site["fingerprint"] == trusted_record["expression_fingerprint"]

    app_tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    matching_expressions: list[ast.AST] = []
    for call in (node for node in ast.walk(app_tree) if isinstance(node, ast.Call)):
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "st"
            and call.func.attr == "html"
            and not call.keywords
        ):
            continue
        expression = call.args[0] if len(call.args) == 1 else None
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


def test_streamlit_container_html_sinks_are_inventoried_and_fail_closed() -> None:
    source = '''
def render(payload, column):
    st.html(build_theme())
    st.sidebar.html(payload)
    column.html(payload)
    st.container().html(payload)
    st.columns(2)[0].html(payload)
    st.markdown(payload, unsafe_allow_html=True)
    render_html(payload)
'''
    shifted = "\n\n\n" + source
    first = inventory.scan_ui_source(source, "ui/html_surface.py")["unsafe_html"]
    second = inventory.scan_ui_source(shifted, "ui/html_surface.py")["unsafe_html"]

    assert [item["call_kind"] for item in first] == [
        "st.html",
        "st.sidebar.html",
        "column.html",
        "st.container().html",
        "st.columns()[].html",
        "st.markdown",
    ]
    assert [item["site_id"] for item in first] == [
        item["site_id"] for item in second
    ]
    html_site = first[0]
    assert html_site["expression_category"] == "call"
    assert html_site["static"] is False
    _expect_inventory_error(
        lambda: inventory.require_classified_unsafe_sites(
            {"unsafe_html": [html_site]}, []
        ),
        "new unclassified unsafe HTML sites",
    )


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


def test_ux1b_release_evidence_mutations_fail_closed() -> None:
    classification = json.loads(UX1B_CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(UX1B_PRE_RELEASE_VERIFICATION_PATH.read_text(encoding="utf-8"))
    reconciliation = json.loads(
        UX1B_CURRENT_HEAD_RECONCILIATION_PATH.read_text(encoding="utf-8")
    )
    wrong_sha256 = "1" * 64

    receipt_mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda value: value.__setitem__("status", "PRE_RELEASE_TECHNICAL_PASS"),
        lambda value: value.__setitem__("status", "ACCEPTED"),
        lambda value: value["artifacts"]["final_posttheme"].__setitem__(
            "manifest_sha256", wrong_sha256
        ),
        lambda value: value["artifacts"]["pretheme"].__setitem__(
            "manifest_sha256", wrong_sha256
        ),
        lambda value: value["artifacts"]["theme_gallery"].__setitem__(
            "manifest_sha256", wrong_sha256
        ),
        lambda value: value["capture_stack"].__setitem__(
            "capture_stack_digest", wrong_sha256
        ),
        lambda value: value["verification"]["visual_review"].__setitem__(
            "status", "FAIL"
        ),
        lambda value: value["verification"]["processes"].__setitem__(
            "browser_workers_quiescent", False
        ),
        lambda value: value["security_scan"][
            "artifact_sensitive_pattern_files"
        ].__setitem__("openai_style_token", 99),
        lambda value: value["failed_attempts_retained"][0].__setitem__(
            "manifest_sha256", wrong_sha256
        ),
        lambda value: value["failed_attempts_retained"][0].__setitem__(
            "status", "passed"
        ),
        lambda value: value["rollback_rehearsal"].__setitem__(
            "base_commit", "0" * 40
        ),
        lambda value: (
            value["source_transactions"]["formal_mirror"].__setitem__(
                "digest_start", wrong_sha256
            ),
            value["source_transactions"]["formal_mirror"].__setitem__(
                "digest_end", wrong_sha256
            ),
        ),
        lambda value: value["source_transactions"][
            "legacy_compatibility_projection"
        ].__setitem__("digest", wrong_sha256),
        lambda value: value["verification"]["pretheme_comparison"].__setitem__(
            "canonical_non_color_projection_sha256", wrong_sha256
        ),
        lambda value: value["rollback_rehearsal"].__setitem__(
            "builder_css_sha256", wrong_sha256
        ),
        lambda value: value["current_head_reconciliation"].__setitem__(
            "sha256", wrong_sha256
        ),
        lambda value: value["test_infrastructure_batch"].__setitem__(
            "production_rollback_excluded", False
        ),
    )
    for mutate in receipt_mutations:
        changed_receipt = copy.deepcopy(receipt)
        mutate(changed_receipt)
        _expect_assertion(
            lambda candidate=changed_receipt: _validate_ux1b_pre_release_receipt(
                candidate
            )
        )

    reconciliation_mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda value: value["merge"].__setitem__("merge_commit", "0" * 40),
        lambda value: value["scope"]["formal_source_projection_files_changed"].append(
            "scripts/ui_ux_inventory.py"
        ),
        lambda value: value["source_binding"].__setitem__(
            "unchanged_by_main_merge", False
        ),
    )
    for mutate in reconciliation_mutations:
        changed_reconciliation = copy.deepcopy(reconciliation)
        mutate(changed_reconciliation)
        _expect_assertion(
            lambda candidate=changed_reconciliation: (
                _validate_ux1b_current_head_reconciliation(candidate, receipt)
            )
        )

    changed_receipt_hash = copy.deepcopy(classification)
    changed_receipt_hash["release_evidence"]["pre_release_verification"][
        "sha256"
    ] = wrong_sha256
    _expect_assertion(
        lambda: _validate_ux1b_release_evidence(changed_receipt_hash)
    )

    changed_reconciliation_hash = copy.deepcopy(classification)
    changed_reconciliation_hash["release_evidence"]["current_head_reconciliation"][
        "sha256"
    ] = wrong_sha256
    _expect_assertion(
        lambda: _validate_ux1b_release_evidence(changed_reconciliation_hash)
    )

    pending_with_closure = copy.deepcopy(classification)
    pending_with_closure["release_evidence"]["release_closure"] = {
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-release-closure-2026-09-02.json",
        "sha256": "0" * 64,
    }
    _expect_assertion(
        lambda: _validate_ux1b_release_evidence(pending_with_closure)
    )

    accepted_without_closure = copy.deepcopy(classification)
    accepted_without_closure["state"] = "accepted"
    _expect_assertion(
        lambda: _validate_ux1b_release_evidence(accepted_without_closure)
    )

    _expect_assertion(
        lambda: _validate_ux1b_release_closure(
            {"schema_version": "quant-radar-ui-ux-ux1b-release-closure/v1"},
            classification["release_evidence"]["pre_release_verification"],
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
    st.sidebar.html("<b>new surface</b>")
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
        test_streamlit_container_html_sinks_are_inventoried_and_fail_closed,
        test_repository_unsafe_inventory_is_deterministic_and_relative,
        test_versioned_baseline_contract_and_evidence_schema,
        test_primary_action_full_call_projection_and_mutations_fail_closed,
        test_ux1b_prechange_and_forward_mutations_fail_closed,
        test_ux1b_release_evidence_mutations_fail_closed,
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
