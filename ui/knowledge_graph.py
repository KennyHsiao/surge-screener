"""Knowledge network view.

Read-only graph of the Obsidian vault under knowledge/. The page is designed for
validation decisions: raw positive readings on blocked factors stay visually and
semantically exploratory.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts import knowledge_graph as kg

from . import _shared

TYPE_COLOR = {
    "dimension": _shared.PURPLE,
    "factor": _shared.BLUE,
    "paper": _shared.GREEN,
    "moc": _shared.MUTED,
    "note": _shared.MUTED,
}
STATUS_COLOR = {
    "validated": _shared.GREEN,
    "exploratory": _shared.AMBER,
    "weak": _shared.BLUE,
    "noise": _shared.MUTED,
    "contrarian": _shared.AMBER,
    "seed": _shared.MUTED,
    "index": _shared.PURPLE,
}
TYPE_LABEL = {
    "dimension": "維度",
    "factor": "因子",
    "paper": "文獻",
    "moc": "MOC",
    "note": "筆記",
}
NODE_SYMBOL = {
    "dimension": "square",
    "factor": "circle",
    "paper": "diamond",
    "moc": "hexagon",
    "note": "circle-open",
}
EDGE_COLOR = {
    "belongs_to_dimension": "rgba(171,99,250,0.32)",
    "evidence": "rgba(0,204,150,0.38)",
    "references": "rgba(139,147,167,0.24)",
    "index_link": "rgba(139,147,167,0.12)",
}
EDGE_LABEL = {
    "belongs_to_dimension": "隸屬維度",
    "evidence": "文獻依據",
    "references": "交叉引用",
    "index_link": "索引連線",
}
STATUS_LABEL = {
    "validated": "已驗證",
    "exploratory": "探索性",
    "weak": "弱訊號",
    "noise": "雜訊",
    "contrarian": "反向",
    "seed": "種子",
    "index": "索引",
}
DIM_COLOR = {
    "Dim1": "#ef5350",
    "Dim2": "#ff9f43",
    "Dim3": "#26c6da",
    "Dim4": "#2ecc71",
    "Dim5": "#ab63fa",
    "Dim6": "#f4d03f",
    "Dim7": "#5dade2",
    "Other": _shared.MUTED,
    "framework": "#c084fc",
    "meta": "#94a3b8",
}
STATUS_LINE = {
    "validated": "rgba(0,204,150,0.92)",
    "exploratory": "rgba(255,161,90,0.88)",
    "weak": "rgba(99,110,250,0.88)",
    "noise": "rgba(139,147,167,0.72)",
    "contrarian": "rgba(239,85,59,0.82)",
    "seed": "rgba(255,255,255,0.48)",
    "index": "rgba(171,99,250,0.72)",
}


@st.cache_data(ttl=60, show_spinner=False)
def _load_graph() -> dict:
    return kg.build_graph()


def _order_key(node: dict) -> tuple:
    dim = str(node.get("dimension") or "")
    try:
        dim_rank = kg.DIM_ORDER.index(dim)
    except ValueError:
        dim_rank = len(kg.DIM_ORDER)
    type_rank = {"moc": 0, "dimension": 1, "factor": 2, "paper": 3}.get(node.get("type"), 4)
    status_rank = {"validated": 0, "weak": 1, "exploratory": 2, "contrarian": 3,
                   "noise": 4, "seed": 5, "index": 6}.get(str(node.get("status")), 7)
    return (dim_rank, type_rank, status_rank, str(node.get("label") or node.get("id")))


def _filtered_graph(graph: dict, types: list[str], dims: list[str], statuses: list[str],
                    hide_moc: bool, focus: str | None) -> tuple[list[dict], list[dict]]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id = {n["id"]: n for n in nodes}

    keep = set()
    for n in nodes:
        if hide_moc and n.get("type") == "moc":
            continue
        if types and n.get("type") not in types:
            continue
        if dims and n.get("dimension") and n.get("dimension") not in dims:
            continue
        if statuses and n.get("status") not in statuses:
            continue
        keep.add(n["id"])

    if focus and focus in by_id:
        neighbors = {focus}
        for e in edges:
            if e["source"] == focus:
                neighbors.add(e["target"])
            if e["target"] == focus:
                neighbors.add(e["source"])
        keep &= neighbors

    out_nodes = [n for n in nodes if n["id"] in keep]
    out_ids = {n["id"] for n in out_nodes}
    out_edges = [e for e in edges if e["source"] in out_ids and e["target"] in out_ids]
    return sorted(out_nodes, key=_order_key), out_edges


def _node_dimension(node: dict) -> str:
    if node.get("type") == "dimension":
        return str(node.get("id") or "Other")
    return str(node.get("dimension") or "Other")


def _stable_float(text: str, salt: str) -> float:
    digest = hashlib.sha256(f"{salt}:{text}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _dimension_order(nodes: list[dict]) -> list[str]:
    dims = {_node_dimension(n) for n in nodes}
    ordered = [d for d in kg.DIM_ORDER if d in dims]
    ordered += sorted(d for d in dims if d not in ordered and d != "Other")
    if "Other" in dims and "Other" not in ordered:
        ordered.append("Other")
    return ordered


def _nebula_initial_positions(nodes: list[dict]) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    dims = _dimension_order(nodes)
    anchors: dict[str, tuple[float, float]] = {}
    if not dims:
        return {}, {}

    for i, dim in enumerate(dims):
        # A flattened ring mirrors Obsidian's graph cloud while keeping clusters readable.
        angle = (2 * math.pi * i / max(len(dims), 1)) - math.pi * 0.72
        anchors[dim] = (2.65 * math.cos(angle), 1.72 * math.sin(angle))

    positions: dict[str, tuple[float, float]] = {}
    for n in nodes:
        node_id = str(n["id"])
        dim = _node_dimension(n)
        cx, cy = anchors.get(dim, (0.0, 0.0))
        node_type = str(n.get("type") or "")
        if node_type == "dimension":
            positions[node_id] = (cx, cy)
            continue
        if node_type == "moc":
            positions[node_id] = (0.0, 0.0)
            continue
        radius = {"factor": 0.48, "paper": 0.88, "note": 0.32}.get(node_type, 0.64)
        jitter_angle = _stable_float(node_id, "angle") * 2 * math.pi
        jitter_radius = radius * (0.32 + 0.82 * _stable_float(node_id, "radius"))
        positions[node_id] = (
            cx + math.cos(jitter_angle) * jitter_radius,
            cy + math.sin(jitter_angle) * jitter_radius,
        )
    return positions, anchors


def _nebula_layout(nodes: list[dict], edges: list[dict]) -> dict[str, tuple[float, float]]:
    if not nodes:
        return {}

    positions, anchors = _nebula_initial_positions(nodes)
    ids = [str(n["id"]) for n in nodes]
    by_id = {str(n["id"]): n for n in nodes}
    fixed = {str(n["id"]) for n in nodes if n.get("type") in ("dimension", "moc")}
    n_count = len(ids)
    k = math.sqrt(18.0 / max(n_count, 1))
    edge_weight = {
        "belongs_to_dimension": 1.15,
        "evidence": 1.35,
        "references": 0.72,
        "index_link": 0.52,
    }

    links: list[tuple[str, str, float]] = []
    link_degree: Counter = Counter()
    for e in edges:
        source, target = str(e["source"]), str(e["target"])
        if source in positions and target in positions:
            links.append((source, target, edge_weight.get(str(e.get("type")), 0.8)))
            link_degree[source] += 1
            link_degree[target] += 1

    for step in range(150):
        disp = {node_id: [0.0, 0.0] for node_id in ids}

        for i, a in enumerate(ids):
            ax, ay = positions[a]
            for b in ids[i + 1:]:
                bx, by = positions[b]
                dx, dy = ax - bx, ay - by
                dist = math.hypot(dx, dy) or 0.001
                force = ((k * k) / dist) * 0.26
                ux, uy = dx / dist, dy / dist
                disp[a][0] += ux * force
                disp[a][1] += uy * force
                disp[b][0] -= ux * force
                disp[b][1] -= uy * force

        for source, target, weight in links:
            sx, sy = positions[source]
            tx, ty = positions[target]
            dx, dy = sx - tx, sy - ty
            dist = math.hypot(dx, dy) or 0.001
            force = (dist * dist / k) * weight * 0.17
            ux, uy = dx / dist, dy / dist
            disp[source][0] -= ux * force
            disp[source][1] -= uy * force
            disp[target][0] += ux * force
            disp[target][1] += uy * force

        for node_id in ids:
            node = by_id[node_id]
            dim = _node_dimension(node)
            ax, ay = anchors.get(dim, (0.0, 0.0))
            px, py = positions[node_id]
            pull = 0.038 if node.get("type") == "factor" else 0.018
            if node.get("type") == "paper":
                pull = 0.016
            if link_degree[node_id] == 0:
                pull = max(pull, 0.07)
            disp[node_id][0] += (ax - px) * pull
            disp[node_id][1] += (ay - py) * pull
            disp[node_id][0] += (0.0 - px) * 0.0025
            disp[node_id][1] += (0.0 - py) * 0.0025

        temp = 0.26 * (1.0 - step / 150)
        for node_id in ids:
            if node_id in fixed:
                continue
            dx, dy = disp[node_id]
            dist = math.hypot(dx, dy) or 0.001
            step_len = min(dist, temp)
            px, py = positions[node_id]
            positions[node_id] = (px + dx / dist * step_len, py + dy / dist * step_len)

    for node_id, (px, py) in list(positions.items()):
        positions[node_id] = (math.tanh(px / 4.3) * 3.55, math.tanh(py / 3.4) * 2.65)
    return positions


def _edge_degree(edges: list[dict]) -> Counter:
    degree: Counter = Counter()
    for e in edges:
        degree[str(e["source"])] += 1
        degree[str(e["target"])] += 1
    return degree


def _nebula_text(node: dict, degree: int, label_mode: str, focus: str | None) -> str:
    if label_mode == "無":
        return ""
    node_id = str(node["id"])
    label = str(node.get("label") or node_id)
    if focus and node_id == focus:
        return label if len(label) <= 24 else label[:23] + "..."
    if label_mode == "全部":
        return label if len(label) <= 22 else label[:21] + "..."
    if label_mode == "因子" and node.get("type") in ("dimension", "factor"):
        return label if len(label) <= 22 else label[:21] + "..."
    if node.get("type") == "dimension" or degree >= 7:
        return label if len(label) <= 20 else label[:19] + "..."
    return ""


def _nebula_figure(nodes: list[dict], edges: list[dict], label_mode: str,
                   edge_opacity: float, focus: str | None) -> go.Figure:
    positions = _nebula_layout(nodes, edges)
    degree = _edge_degree(edges)
    by_id = {str(n["id"]): n for n in nodes}
    fig = go.Figure()

    for edge_type in ("index_link", "references", "belongs_to_dimension", "evidence"):
        edge_x, edge_y = [], []
        for e in edges:
            if e.get("type") != edge_type:
                continue
            source, target = str(e["source"]), str(e["target"])
            if source not in positions or target not in positions:
                continue
            x0, y0 = positions[source]
            x1, y1 = positions[target]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
        if not edge_x:
            continue
        base = edge_opacity
        if edge_type == "references":
            base *= 0.7
        if edge_type == "index_link":
            base *= 0.42
        color = f"rgba(210,218,232,{base:.3f})"
        if edge_type == "evidence":
            color = f"rgba(0,204,150,{min(base * 1.4, 0.7):.3f})"
        elif edge_type == "belongs_to_dimension":
            color = f"rgba(171,99,250,{min(base * 1.1, 0.55):.3f})"
        fig.add_trace(go.Scattergl(
            x=edge_x, y=edge_y, mode="lines", hoverinfo="skip",
            line=dict(color=color, width=1.0 if edge_type != "evidence" else 1.25),
            name=EDGE_LABEL.get(edge_type, edge_type),
            showlegend=False,
        ))

    for node_type in ("paper", "note", "factor", "dimension", "moc"):
        subset = [n for n in nodes if n.get("type") == node_type and str(n["id"]) in positions]
        if not subset:
            continue
        x, y, text, hover, colors, sizes, line_colors, line_widths, opacities = [], [], [], [], [], [], [], [], []
        for n in subset:
            node_id = str(n["id"])
            px, py = positions[node_id]
            dim = _node_dimension(n)
            status = str(n.get("status") or "")
            label = str(n.get("label") or node_id)
            deg = int(degree[node_id])
            is_focus = bool(focus and node_id == focus)
            x.append(px)
            y.append(py)
            text.append(_nebula_text(n, deg, label_mode, focus))
            colors.append(DIM_COLOR.get(dim, DIM_COLOR.get("Other", _shared.MUTED)))
            base_size = {"dimension": 26, "factor": 12, "paper": 7, "moc": 18, "note": 8}.get(node_type, 8)
            sizes.append(base_size + min(deg, 18) * (0.75 if node_type != "paper" else 0.36) + (8 if is_focus else 0))
            line_colors.append("#ffffff" if is_focus else STATUS_LINE.get(status, "rgba(255,255,255,0.45)"))
            line_widths.append(2.4 if is_focus else 1.2 if node_type in ("dimension", "factor") else 0.6)
            opacities.append(0.42 if n.get("blocked") else 0.9)
            hover.append(
                f"<b>{label}</b><br>"
                f"id: {node_id}<br>"
                f"type: {TYPE_LABEL.get(str(node_type), node_type)}<br>"
                f"dimension: {dim}<br>"
                f"degree: {deg}<br>"
                f"status: {STATUS_LABEL.get(status, status) or '-'}<br>"
                f"blocked: {n.get('blocked')}<br>"
                f"path: {n.get('path')}"
            )
        fig.add_trace(go.Scattergl(
            x=x, y=y, mode="markers+text", name=TYPE_LABEL.get(node_type, node_type),
            text=text, textposition="top center", hovertext=hover, hoverinfo="text",
            marker=dict(
                size=sizes, color=colors, opacity=opacities,
                line=dict(color=line_colors, width=line_widths),
            ),
            textfont=dict(size=10, color="#f8fafc"),
        ))

    counts_by_dim = Counter(_node_dimension(n) for n in nodes)
    for dim, count in sorted(counts_by_dim.items(), key=lambda item: (kg.DIM_ORDER.index(item[0]) if item[0] in kg.DIM_ORDER else 99, item[0])):
        cluster_nodes = [str(n["id"]) for n in nodes if _node_dimension(n) == dim and str(n["id"]) in positions]
        if not cluster_nodes:
            continue
        xs = [positions[node_id][0] for node_id in cluster_nodes]
        ys = [positions[node_id][1] for node_id in cluster_nodes]
        fig.add_annotation(
            x=sum(xs) / len(xs), y=sum(ys) / len(ys), text=f"{dim} · {count}",
            showarrow=False, font=dict(size=11, color=DIM_COLOR.get(dim, _shared.MUTED)),
            bgcolor="rgba(14,17,23,0.72)", bordercolor="rgba(255,255,255,0.08)", borderpad=4,
        )

    fig.update_layout(
        height=820,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="#0a0d12",
        plot_bgcolor="#0a0d12",
        xaxis=dict(visible=False, zeroline=False, showgrid=False, range=[-3.95, 3.95]),
        yaxis=dict(visible=False, zeroline=False, showgrid=False, range=[-2.95, 2.95]),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        dragmode="pan",
    )
    return fig


def _layout(nodes: list[dict]) -> tuple[dict[str, tuple[float, float]], list[dict]]:
    grouped: dict[str, dict[str, list[dict]]] = {}
    for n in nodes:
        dim = str(n.get("dimension") or "")
        if n.get("type") == "dimension":
            dim = n["id"]
        grouped.setdefault(dim or "Other", {}).setdefault(str(n.get("type")), []).append(n)

    positions: dict[str, tuple[float, float]] = {}
    dim_order = [d for d in kg.DIM_ORDER if d in grouped]
    dim_order += sorted(d for d in grouped if d not in dim_order and d != "Other")
    if "Other" in grouped and "Other" not in dim_order:
        dim_order.append("Other")

    bands: list[dict] = []
    y_cursor = 0.0
    x_by_type = {"moc": -0.7, "dimension": 0.0, "factor": 1.65, "paper": 3.45, "note": 4.2}
    for dim in dim_order:
        bucket = grouped[dim]
        row_count = max(len(bucket.get("factor", [])), len(bucket.get("paper", [])), 1)
        height = max(1.6, row_count * 0.52)
        y_top = y_cursor + 0.65
        y_bottom = y_cursor - height + 0.1
        center_y = (y_top + y_bottom) / 2
        bands.append({"dim": dim, "y0": y_bottom, "y1": y_top})
        for node_type, ns in bucket.items():
            ordered = sorted(ns, key=_order_key)
            if node_type == "dimension":
                for n in ordered:
                    positions[n["id"]] = (x_by_type["dimension"], center_y)
                continue
            x = x_by_type.get(node_type, x_by_type["note"])
            offset = -0.26 * (len(ordered) - 1)
            for i, n in enumerate(ordered):
                positions[n["id"]] = (x, center_y + offset + i * 0.52)
        y_cursor = y_bottom - 0.45

    moc_nodes = [n for n in nodes if n.get("type") == "moc"]
    for i, n in enumerate(moc_nodes):
        positions[n["id"]] = (-1.0, 0.0 - i * 0.5)
    return positions, bands


def _figure(nodes: list[dict], edges: list[dict]) -> go.Figure:
    pos, bands = _layout(nodes)
    fig = go.Figure()

    for i, band in enumerate(bands):
        fill = "rgba(255,255,255,0.035)" if i % 2 == 0 else "rgba(255,255,255,0.015)"
        fig.add_shape(
            type="rect", x0=-0.35, x1=4.0, y0=band["y0"], y1=band["y1"],
            line=dict(width=0), fillcolor=fill, layer="below",
        )
        fig.add_annotation(
            x=-0.28, y=band["y1"] - 0.2, text=band["dim"], showarrow=False,
            xanchor="left", yanchor="top", font=dict(size=11, color="#9aa4b8"),
        )

    for edge_type in ("belongs_to_dimension", "evidence", "references", "index_link"):
        edge_x, edge_y = [], []
        for e in edges:
            if e.get("type") != edge_type:
                continue
            if e["source"] not in pos or e["target"] not in pos:
                continue
            x0, y0 = pos[e["source"]]
            x1, y1 = pos[e["target"]]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]
        if not edge_x:
            continue
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines", hoverinfo="skip",
            line=dict(color=EDGE_COLOR.get(edge_type, "rgba(139,147,167,0.2)"),
                      width=1.4 if edge_type == "evidence" else 1),
            name=EDGE_LABEL.get(edge_type, edge_type),
            showlegend=True,
        ))

    for node_type in sorted({n.get("type") for n in nodes}):
        subset = [n for n in nodes if n.get("type") == node_type and n["id"] in pos]
        if not subset:
            continue
        x, y, hover, text, colors, sizes, symbols, opacities = [], [], [], [], [], [], [], []
        for n in subset:
            px, py = pos[n["id"]]
            x.append(px)
            y.append(py)
            label = str(n.get("label") or n["id"])
            if node_type == "paper":
                text.append("")
            elif node_type == "factor":
                text.append(n["id"] if len(n["id"]) <= 24 else n["id"][:23] + "...")
            else:
                text.append(label if len(label) <= 22 else label[:21] + "...")
            status = str(n.get("status") or "")
            colors.append(STATUS_COLOR.get(status, TYPE_COLOR.get(node_type, _shared.MUTED)))
            sizes.append(22 if node_type == "dimension" else 15 if node_type == "factor" else 10)
            symbols.append(NODE_SYMBOL.get(str(node_type), "circle"))
            opacities.append(0.55 if n.get("blocked") else 0.94)
            hover.append(
                f"<b>{label}</b><br>"
                f"id: {n['id']}<br>"
                f"type: {TYPE_LABEL.get(str(node_type), node_type)}<br>"
                f"dimension: {n.get('dimension') or '-'}<br>"
                f"status: {STATUS_LABEL.get(status, status) or '-'}<br>"
                f"blocked: {n.get('blocked')}<br>"
                f"raw verdict: {n.get('verdict_raw') or '-'}<br>"
                f"path: {n.get('path')}"
            )
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="markers+text", name=TYPE_LABEL.get(str(node_type), str(node_type)),
            text=text, textposition="top center", hovertext=hover, hoverinfo="text",
            marker=dict(size=sizes, color=colors, symbol=symbols, opacity=opacities,
                        line=dict(color="rgba(255,255,255,0.72)", width=0.9)),
            textfont=dict(size=10, color="#d7dde8"),
        ))

    for x, text in ((0, "維度"), (1.65, "因子"), (3.45, "文獻")):
        fig.add_annotation(x=x, y=0.95, yref="paper", text=text, showarrow=False,
                           font=dict(size=12, color="#d7dde8"))

    fig.update_layout(
        height=760,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-0.55, 3.95]),
        yaxis=dict(visible=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def _node_table(nodes: list[dict]) -> pd.DataFrame:
    rows = []
    for n in nodes:
        if n.get("type") not in ("factor", "paper"):
            continue
        lift = n.get("lift_exploratory")
        if isinstance(lift, (int, float)):
            lift = f"{lift:.2f}"
        rows.append({
            "id": n["id"],
            "type": TYPE_LABEL.get(str(n.get("type")), n.get("type")),
            "dimension": n.get("dimension") or "",
            "horizon": n.get("horizon") or "",
            "status": n.get("status") or "",
            "blocked": bool(n.get("blocked")),
            "lift_exploratory": str(lift or ""),
            "runway": n.get("runway_verdict") or "",
            "path": n.get("path") or "",
        })
    return pd.DataFrame(rows)


def render() -> None:
    st.title("知識網路")
    st.caption("文獻、因子、維度與驗證狀態的唯讀圖像化。blocked 的結果只作探索性參考。")

    graph = _load_graph()
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    diagnostics = graph.get("diagnostics", {})

    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "節點", len(nodes))
    _shared.metric_card(c2, "連線", len(edges))
    _shared.metric_card(c3, "因子", sum(1 for n in nodes if n.get("type") == "factor"))
    _shared.metric_card(c4, "blocked", sum(1 for n in nodes if n.get("blocked")))

    _shared.chips_row([
        ("紅=Dim1", DIM_COLOR["Dim1"]),
        ("橘=Dim2", DIM_COLOR["Dim2"]),
        ("青=Dim3", DIM_COLOR["Dim3"]),
        ("綠=Dim4", DIM_COLOR["Dim4"]),
        ("紫=Dim5", DIM_COLOR["Dim5"]),
        ("淡色=blocked", _shared.AMBER),
    ])

    dims = sorted({n.get("dimension") for n in nodes if n.get("dimension")})
    statuses = sorted({n.get("status") for n in nodes if n.get("status")})
    types = sorted({n.get("type") for n in nodes if n.get("type")})
    node_options = [""] + [n["id"] for n in sorted(nodes, key=_order_key)]

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.1, 1.2, 1.2, 1.5])
        default_types = [t for t in ("dimension", "factor", "paper") if t in types]
        sel_types = c1.multiselect("節點", types, default=default_types)
        sel_dims = c2.multiselect("維度", dims, default=dims)
        sel_statuses = c3.multiselect("狀態", statuses, default=statuses)
        focus = c4.selectbox("Focus 1-hop", node_options, format_func=lambda x: "全部" if not x else x)
        hide_moc = st.checkbox("隱藏 MOC/index 連線", value=True)
        c5, c6, c7 = st.columns([1.1, 1.1, 1.2])
        view_mode = c5.segmented_control(
            "視圖", ["星雲圖", "驗證泳道"], default="星雲圖", key="kg_view_mode")
        label_mode = c6.segmented_control(
            "標籤", ["核心", "因子", "全部", "無"], default="核心", key="kg_label_mode")
        edge_opacity = c7.slider("連線", min_value=0.03, max_value=0.36, value=0.14,
                                 step=0.01, key="kg_edge_opacity")

    view_nodes, view_edges = _filtered_graph(
        graph, sel_types, sel_dims, sel_statuses, hide_moc, focus or None)
    if not view_nodes:
        st.info("目前篩選條件下沒有節點。")
        return

    st.caption(f"目前視圖: {len(view_nodes)} 個實際 vault 節點 / {len(view_edges)} 條連線。")
    if view_mode == "星雲圖":
        st.plotly_chart(
            _nebula_figure(view_nodes, view_edges, label_mode, edge_opacity, focus or None),
            width="stretch",
            config={"scrollZoom": True, "displaylogo": False},
        )
    else:
        st.plotly_chart(_figure(view_nodes, view_edges), width="stretch",
                        config={"scrollZoom": True, "displaylogo": False})

    tab_detail, tab_obsidian, tab_diag = st.tabs(["明細", "Obsidian", "診斷"])
    with tab_detail:
        df = _node_table(view_nodes)
        if df.empty:
            st.info("目前視圖沒有 factor 或 paper 節點。")
        else:
            st.dataframe(df, hide_index=True, width="stretch")

    with tab_obsidian:
        st.markdown(f"**Vault path**: `{kg.VAULT}`")
        st.markdown(
            "- 已結合 Obsidian: `knowledge/` 是原生 vault, 用標準 `[[wikilinks]]` 與 YAML `tags`。\n"
            "- 不需要外掛；用 Obsidian 的 Graph View / Local Graph 即可看完整關係。\n"
            "- Graph View 可用 `tag:#kg/type/factor`、`tag:#kg/status/exploratory`、"
            "`tag:#kg/block/blocked` 快速聚焦。\n"
            "- 從 `MOC.md` 看全域圖；從單一 factor card 開 Local Graph 看 1-hop 文獻與維度。"
        )

    with tab_diag:
        unresolved = diagnostics.get("unresolved_links") or []
        dupes = diagnostics.get("duplicate_ids") or []
        if not unresolved and not dupes:
            st.success("沒有 unresolved wikilink 或 duplicate id。")
        if unresolved:
            st.warning(f"{len(unresolved)} 個 unresolved wikilink")
            st.dataframe(pd.DataFrame(unresolved), hide_index=True, width="stretch")
        if dupes:
            st.error("Duplicate ids: " + ", ".join(dupes))
