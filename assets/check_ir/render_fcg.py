#!/usr/bin/env python3
"""
Improved renderer for fcg.json (fixed cycle-safe layout).

Fixes:
- robust fallback layout even when the graph contains cycles
- uses SCC condensation graph to assign layers
- cleaner overview graph
- shorter node labels
- no cluttered edge labels in PNG/SVG
- still exports detailed DOT / Mermaid files

Usage:
  python render_fcg_improved_v2.py --input assets/spec_ir/fcg.json
  python render_fcg_improved_v2.py --input assets/spec_ir/fcg.json --outdir assets/spec_ir/fcg_vis
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import networkx as nx


# ----------------------------
# Basic helpers
# ----------------------------

def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    return text.strip("_") or "node"


def read_fcg(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("fcg.json top-level must be an object")
    if "nodes" not in data or "edges" not in data:
        raise ValueError("fcg.json must contain 'nodes' and 'edges'")
    if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
        raise ValueError("'nodes' and 'edges' must both be arrays")
    return data


def build_graph(data: Dict) -> nx.DiGraph:
    g = nx.DiGraph()
    for node in data["nodes"]:
        node_id = node["node_id"]
        g.add_node(
            node_id,
            name=node.get("name", node_id),
            label=node.get("label", ""),
            page_start=node.get("page_start", 0),
            page_end=node.get("page_end", 0),
            node_type=node.get("node_type", "internal_function"),
        )

    for edge in data["edges"]:
        src = edge["source"]
        tgt = edge["target"]
        evidence = edge.get("evidence", {})
        g.add_edge(
            src,
            tgt,
            relation=edge.get("relation", ""),
            evidence_page=evidence.get("page", 0),
            evidence_text=evidence.get("text", ""),
        )

    return g


# ----------------------------
# Label cleaning
# ----------------------------

ALG_RE = re.compile(r"Algorithm\s+(\d+)", re.IGNORECASE)


def compact_alg_label(label: str) -> str:
    if not label:
        return ""
    m = ALG_RE.search(label)
    if m:
        return f"Alg {m.group(1)}"
    return label.strip()


def short_function_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    if "(" in name:
        name = name.split("(", 1)[0].strip()
    name = name.replace("⁻¹", "_inverse")
    name = name.replace("^-1", "_inverse")
    name = name.replace("−1", "_inverse")
    name = name.replace(" ", "_")
    return name


def wrap_label(text: str, width: int = 18) -> str:
    if not text:
        return ""
    parts = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    return "\n".join(parts) if parts else text


def node_display_label(node_id: str, attrs: Dict, show_alg_label: bool = True) -> str:
    raw_name = attrs.get("name", node_id)
    func_name = short_function_name(raw_name)
    func_name = wrap_label(func_name, width=18)

    alg_label = compact_alg_label(attrs.get("label", ""))
    if show_alg_label and alg_label:
        return f"{func_name}\n[{alg_label}]"
    return func_name


# ----------------------------
# DOT / Mermaid exports
# ----------------------------

def write_dot(g: nx.DiGraph, outpath: Path, graph_name: str = "FCG") -> None:
    lines: List[str] = []
    lines.append(f'digraph "{graph_name}" {{')
    lines.append('  rankdir=LR;')
    lines.append('  graph [splines=true, overlap=false, concentrate=true, newrank=true, ranksep="1.0", nodesep="0.55", pad="0.25"];')
    lines.append('  node [style="rounded,filled", penwidth=1.6, fontname="Helvetica", fontsize=11, margin="0.16,0.10"];')
    lines.append('  edge [color="#7a7a7a", fontname="Helvetica", fontsize=9, penwidth=1.4, arrowsize=0.9];')
    lines.append("")

    for node_id, attrs in g.nodes(data=True):
        label = node_display_label(node_id, attrs, show_alg_label=True).replace('"', '\\"').replace("\n", "\\n")
        if attrs.get("node_type") == "internal_function":
            lines.append(f'  "{node_id}" [label="{label}", shape=box, fillcolor="#5b8fd9", fontcolor="white"];')
        else:
            lines.append(f'  "{node_id}" [label="{label}", shape=ellipse, fillcolor="#d98b3a", fontcolor="white"];')

    lines.append("")
    for src, tgt, attrs in g.edges(data=True):
        relation = attrs.get("relation", "")
        page = attrs.get("evidence_page", 0)
        evidence_text = attrs.get("evidence_text", "")
        tooltip = f"page={page}; {evidence_text}".replace('"', '\\"')
        if relation:
            lines.append(f'  "{src}" -> "{tgt}" [label="{relation}", tooltip="{tooltip}"];')
        else:
            lines.append(f'  "{src}" -> "{tgt}" [tooltip="{tooltip}"];')

    lines.append("}")
    outpath.write_text("\n".join(lines), encoding="utf-8")


def write_mermaid(g: nx.DiGraph, outpath: Path) -> None:
    lines: List[str] = []
    lines.append("graph LR")
    lines.append("    classDef internal fill:#5b8fd9,stroke:#2c5ea8,stroke-width:1.5px,color:#fff;")
    lines.append("    classDef external fill:#d98b3a,stroke:#9b5a1d,stroke-width:1.5px,color:#fff;")
    lines.append("")

    for node_id, attrs in g.nodes(data=True):
        display = node_display_label(node_id, attrs, show_alg_label=True).replace("\n", "<br/>").replace('"', "'")
        sid = safe_name(node_id)
        if attrs.get("node_type") == "internal_function":
            lines.append(f'    {sid}["{display}"]')
            lines.append(f"    class {sid} internal;")
        else:
            lines.append(f'    {sid}(("{display}"))')
            lines.append(f"    class {sid} external;")

    lines.append("")
    for src, tgt, attrs in g.edges(data=True):
        relation = attrs.get("relation", "")
        s = safe_name(src)
        t = safe_name(tgt)
        if relation:
            lines.append(f"    {s} -->|{relation}| {t}")
        else:
            lines.append(f"    {s} --> {t}")

    outpath.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------
# Layout helpers for fallback drawing
# ----------------------------

def dag_layers(g: nx.DiGraph) -> Dict[str, int]:
    """
    Cycle-safe layer assignment.

    Strategy:
    - Separate internal and external nodes
    - Build SCC condensation DAG on internal nodes
    - Compute longest-path layers on the condensation DAG
    - Assign every node in the same SCC the same layer
    - Push external primitives to the far right
    """
    internal_nodes = [n for n, a in g.nodes(data=True) if a.get("node_type") == "internal_function"]
    external_nodes = [n for n, a in g.nodes(data=True) if a.get("node_type") != "internal_function"]

    layer: Dict[str, int] = {}

    if internal_nodes:
        sub = g.subgraph(internal_nodes).copy()

        # SCC condensation graph is guaranteed to be a DAG
        sccs = list(nx.strongly_connected_components(sub))
        cond = nx.condensation(sub, sccs)

        comp_layer: Dict[int, int] = {}
        for comp in nx.topological_sort(cond):
            preds = list(cond.predecessors(comp))
            if preds:
                comp_layer[comp] = max(comp_layer[p] for p in preds) + 1
            else:
                comp_layer[comp] = 0

        mapping = cond.graph["mapping"]  # node -> component id
        for node in sub.nodes():
            layer[node] = comp_layer[mapping[node]]

    max_internal = max(layer.values(), default=0)
    for node in external_nodes:
        layer[node] = max_internal + 1

    # Any leftover nodes, just place at layer 0
    for node in g.nodes():
        layer.setdefault(node, 0)

    return layer


def layered_layout(g: nx.DiGraph) -> Dict[str, Tuple[float, float]]:
    layer = dag_layers(g)
    buckets: Dict[int, List[str]] = {}
    for n, lv in layer.items():
        buckets.setdefault(lv, []).append(n)

    pos: Dict[str, Tuple[float, float]] = {}
    x_gap = 4.6
    y_gap = 2.2

    for lv in sorted(buckets):
        nodes = sorted(
            buckets[lv],
            key=lambda n: (
                g.nodes[n].get("node_type", ""),
                short_function_name(g.nodes[n].get("name", n)),
            ),
        )
        count = len(nodes)
        mid = (count - 1) / 2
        for i, n in enumerate(nodes):
            y = -(i - mid) * y_gap
            x = lv * x_gap
            pos[n] = (x, y)

    return pos


# ----------------------------
# Rendering
# ----------------------------

def try_graphviz_render(dot_path: Path, png_path: Path, svg_path: Path) -> bool:
    dot_bin = shutil.which("dot")
    if not dot_bin:
        return False
    try:
        subprocess.run([dot_bin, "-Tsvg", str(dot_path), "-o", str(svg_path)], check=True)
        subprocess.run([dot_bin, "-Tpng", str(dot_path), "-o", str(png_path)], check=True)
        return True
    except Exception:
        return False


def draw_graph_fallback(g: nx.DiGraph, png_path: Path, svg_path: Path, title: str) -> None:
    if len(g.nodes()) == 0:
        raise ValueError("Graph has no nodes")

    pos = layered_layout(g)

    n_nodes = g.number_of_nodes()
    n_cols = len({round(x) for x, _ in pos.values()}) if pos else 1
    width = max(14, min(34, 8 + n_cols * 3.0))
    height = max(9, min(28, 5 + n_nodes * 0.55))

    fig, ax = plt.subplots(figsize=(width, height), dpi=180)
    ax.set_title(title, fontsize=16, fontweight="bold", pad=16)

    internal_nodes = [n for n, a in g.nodes(data=True) if a.get("node_type") == "internal_function"]
    primitive_nodes = [n for n, a in g.nodes(data=True) if a.get("node_type") != "internal_function"]

    nx.draw_networkx_nodes(
        g, pos, nodelist=internal_nodes, node_shape="s",
        node_color="#5b8fd9", node_size=2600, ax=ax,
        edgecolors="#2c5ea8", linewidths=1.6
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=primitive_nodes, node_shape="o",
        node_color="#d98b3a", node_size=2400, ax=ax,
        edgecolors="#9b5a1d", linewidths=1.6
    )

    nx.draw_networkx_edges(
        g, pos, arrows=True, ax=ax,
        width=1.4, edge_color="#8a8a8a",
        arrowsize=16, arrowstyle="-|>",
        connectionstyle="arc3,rad=0.05", alpha=0.8
    )

    labels = {n: node_display_label(n, a, show_alg_label=True) for n, a in g.nodes(data=True)}
    nx.draw_networkx_labels(
        g, pos, labels=labels, font_size=9.5,
        font_weight="bold", font_family="sans-serif", ax=ax
    )

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', label='Internal function',
               markerfacecolor='#5b8fd9', markeredgecolor='#2c5ea8', markersize=12),
        Line2D([0], [0], marker='o', color='w', label='External primitive',
               markerfacecolor='#d98b3a', markeredgecolor='#9b5a1d', markersize=12),
    ]
    ax.legend(handles=legend_elements, loc="upper right", frameon=False, fontsize=10)

    ax.axis("off")
    ax.margins(0.18)
    plt.tight_layout()
    fig.savefig(png_path, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Render fcg.json into cleaner graph outputs.")
    parser.add_argument("--input", default="", help="Path to fcg.json. Default: fcg.json next to this script.")
    parser.add_argument("--outdir", default="", help="Output directory. Default: same directory as the script.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = Path(args.input).resolve() if args.input else (script_dir / "fcg.json")
    outdir = Path(args.outdir).resolve() if args.outdir else script_dir

    if not input_path.exists():
        print(f"Error: fcg.json not found: {input_path}")
        return

    data = read_fcg(input_path)
    graph_name = data.get("graph_name", "function_call_graph")
    source_document = data.get("source_document", input_path.name)

    outdir.mkdir(parents=True, exist_ok=True)

    g = build_graph(data)

    dot_path = outdir / "fcg.dot"
    mmd_path = outdir / "fcg.mmd"
    png_path = outdir / "fcg.png"
    svg_path = outdir / "fcg.svg"

    write_dot(g, dot_path, graph_name=graph_name)
    write_mermaid(g, mmd_path)

    rendered_by_graphviz = try_graphviz_render(dot_path, png_path, svg_path)
    if not rendered_by_graphviz:
        draw_graph_fallback(g, png_path, svg_path, title=f"{graph_name} | {source_document}")

    print(f"Input:  {input_path}")
    print(f"Nodes:  {g.number_of_nodes()}")
    print(f"Edges:  {g.number_of_edges()}")
    print(f"Output directory: {outdir}")
    if rendered_by_graphviz:
        print("Rendered overview with Graphviz.")
    else:
        print("Rendered overview with matplotlib fallback.")
    print("Generated:")
    print(f"  - {dot_path.name}")
    print(f"  - {mmd_path.name}")
    print(f"  - {png_path.name}")
    print(f"  - {svg_path.name}")


if __name__ == "__main__":
    main()
