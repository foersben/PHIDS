#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Interactive Cytoscape.js knowledge graph visualizer for OKF v0.2 bundles.

Generates a standalone, zero-dependency HTML file (`docs/viz.html`) that renders
the complete knowledge graph across `docs/` and `.agents/`, with color-coded node types,
interactive search, filter controls, and concept inspection panels.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^:\s#)]+\.md)(?:#[^)]+)?\)")


def _extract_trust_tier(verified: Any) -> str:
    """Determine trust tier from OKF verified metadata."""
    if not verified:
        return "Unverified"
    v_list = [verified] if isinstance(verified, dict) else verified
    if any(isinstance(v, dict) and str(v.get("by", "")).startswith("human:") for v in v_list):
        return "Human-Reviewed"
    return "Machine-Confirmed"


def _parse_frontmatter_meta(content: str, default_title: str) -> tuple[str, str, str, str, str, str] | None:
    """Parse YAML frontmatter returning (doc_type, title, status, description, trust_tier, body)."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    doc_type = "Concept"
    title = default_title
    status = "stable"
    description = ""
    trust_tier = "Unverified"
    try:
        fm = yaml.safe_load(parts[1])
        if isinstance(fm, dict):
            doc_type = str(fm.get("type", "Concept"))
            title = str(fm.get("title", default_title))
            status = str(fm.get("status", "stable"))
            description = str(fm.get("description", ""))
            trust_tier = _extract_trust_tier(fm.get("verified"))
    except Exception:
        pass
    return doc_type, title, status, description, trust_tier, parts[2]


def _parse_special_doc_meta(file_path: Path, content: str) -> tuple[str, str] | None:
    """Determine doc_type and title for index.md or log.md."""
    if file_path.name == "index.md":
        first_heading = next((line for line in content.splitlines() if line.startswith("#")), None)
        title = first_heading.lstrip("#").strip() if first_heading else file_path.stem
        return "Directory Index", title
    if file_path.name == "log.md":
        return "Update Log", f"{file_path.parent.name.title()} Log"
    return None


def _resolve_outgoing_link(link: str, file_path: Path, root_path: Path) -> str | None:
    """Resolve a relative markdown link to a root-relative posix path."""
    if link.startswith(("http://", "https://", "#")):
        return None
    if link.startswith("/"):
        target = (root_path / link.lstrip("/")).resolve()
    else:
        target = (file_path.parent / link).resolve()

    if target.is_file():
        try:
            return target.relative_to(root_path).as_posix()
        except ValueError:
            return None
    return None


def _extract_outgoing_links(body: str, file_path: Path, root_path: Path) -> list[str]:
    """Find all valid relative markdown links in document body."""
    outgoing: list[str] = []
    for link in MARKDOWN_LINK_PATTERN.findall(body):
        resolved = _resolve_outgoing_link(link, file_path, root_path)
        if resolved:
            outgoing.append(resolved)
    return list(set(outgoing))


def _extract_doc_info(file_path: Path, root_path: Path) -> dict[str, Any] | None:
    """Extract graph node info and outgoing links from a markdown document."""
    try:
        content = file_path.read_text(encoding="utf-8").strip()
    except Exception:
        return None

    rel_id = file_path.relative_to(root_path).as_posix()
    default_title = file_path.stem.replace("_", " ").replace("-", " ").title()
    doc_type = "Document"
    title = default_title
    status = "stable"
    description = ""
    trust_tier = "Unverified"
    body = content

    fm_meta = _parse_frontmatter_meta(content, default_title)
    if fm_meta:
        doc_type, title, status, description, trust_tier, body = fm_meta
    else:
        special = _parse_special_doc_meta(file_path, content)
        if special:
            doc_type, title = special

    links = _extract_outgoing_links(body, file_path, root_path)

    return {
        "id": rel_id,
        "title": title,
        "type": doc_type,
        "status": status,
        "description": description,
        "trust_tier": trust_tier,
        "links": links,
    }


def _collect_markdown_files(root_path: Path, directories: list[str]) -> list[Path]:
    """Collect valid markdown files across target directories, excluding legacy/site files."""
    files: list[Path] = []
    for dir_name in directories:
        dir_path = root_path / dir_name
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            file_posix = md_file.as_posix()
            if "docs/legacy/" not in file_posix and "site/" not in file_posix:
                files.append(md_file)
    return files


def _register_doc_elements(
    info: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    seen_nodes: set[str],
) -> None:
    """Register node and outgoing edges from extracted document info."""
    node_id = info["id"]
    seen_nodes.add(node_id)
    nodes.append(
        {
            "data": {
                "id": node_id,
                "label": info["title"],
                "type": info["type"],
                "status": info["status"],
                "trust_tier": info["trust_tier"],
                "description": info["description"],
            }
        }
    )
    for target_id in info["links"]:
        edges.append(
            {
                "data": {
                    "id": f"{node_id}->{target_id}",
                    "source": node_id,
                    "target": target_id,
                }
            }
        )


def build_graph_data(root_path: Path, directories: list[str]) -> dict[str, Any]:
    """Scan directories and construct node/edge payload for Cytoscape.js."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    for md_file in _collect_markdown_files(root_path, directories):
        info = _extract_doc_info(md_file, root_path)
        if info:
            _register_doc_elements(info, nodes, edges, seen_nodes)

    valid_edges = [e for e in edges if e["data"]["target"] in seen_nodes]
    return {"nodes": nodes, "edges": valid_edges}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PHIDS Knowledge Graph Explorer (OKF v0.2)</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    :root {
      --bg-color: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.85);
      --border-color: rgba(255, 255, 255, 0.12);
      --text-main: #f3f4f6;
      --text-dim: #9ca3af;
      --accent: #ff5722;
      --accent-cyan: #00e5ff;
      --accent-purple: #b388ff;
      --accent-green: #00e676;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-main);
      overflow: hidden;
      display: flex;
      height: 100vh;
      width: 100vw;
    }

    #cy {
      flex: 1;
      height: 100%;
      background: radial-gradient(circle at center, #111827 0%, #030712 100%);
    }

    #sidebar {
      width: 380px;
      height: 100%;
      background: var(--card-bg);
      backdrop-filter: blur(16px);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      padding: 20px;
      z-index: 10;
      box-shadow: -4px 0 24px rgba(0,0,0,0.5);
    }

    .header-title {
      font-size: 1.25rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
    }

    .header-sub {
      font-size: 0.8rem;
      color: var(--text-dim);
      margin-bottom: 16px;
    }

    .search-box {
      width: 100%;
      padding: 10px 14px;
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      color: #fff;
      font-size: 0.9rem;
      margin-bottom: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-box:focus {
      border-color: var(--accent-cyan);
    }

    .stats-row {
      display: flex;
      gap: 10px;
      margin-bottom: 16px;
    }
    .stat-badge {
      flex: 1;
      padding: 8px;
      background: rgba(255,255,255,0.04);
      border-radius: 6px;
      text-align: center;
      font-size: 0.75rem;
      border: 1px solid var(--border-color);
    }
    .stat-badge strong {
      display: block;
      font-size: 1.1rem;
      color: var(--accent-cyan);
    }

    #details-panel {
      flex: 1;
      overflow-y: auto;
      padding-right: 6px;
    }

    .concept-card {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-top: 10px;
    }

    .concept-title {
      font-size: 1.1rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 8px;
    }

    .tag-list {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 12px;
    }
    .tag {
      font-size: 0.7rem;
      padding: 2px 8px;
      border-radius: 12px;
      background: rgba(0, 229, 255, 0.15);
      color: var(--accent-cyan);
      border: 1px solid rgba(0, 229, 255, 0.3);
    }
    .tag.tier {
      background: rgba(0, 230, 118, 0.15);
      color: var(--accent-green);
      border-color: rgba(0, 230, 118, 0.3);
    }

    .concept-desc {
      font-size: 0.85rem;
      line-height: 1.4;
      color: #d1d5db;
      margin-bottom: 14px;
    }

    .meta-item {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-bottom: 4px;
    }
    .meta-item b {
      color: #e5e7eb;
    }
  </style>
</head>
<body>
  <div id="cy"></div>
  <div id="sidebar">
    <div class="header-title">PHIDS Knowledge Graph</div>
    <div class="header-sub">Open Knowledge Format (OKF v0.2) Explorer</div>

    <input type="text" id="search" class="search-box" placeholder="Search concepts, types, rules..." />

    <div class="stats-row">
      <div class="stat-badge"><strong id="node-count">0</strong>Nodes</div>
      <div class="stat-badge"><strong id="edge-count">0</strong>Edges</div>
    </div>

    <div id="details-panel">
      <div style="font-size:0.85rem; color: var(--text-dim); text-align: center; margin-top: 40px;">
        Click any node in the graph to inspect its OKF frontmatter, trust tier, and cross-links.
      </div>
    </div>
  </div>

  <script>
    const graphData = GRAPH_DATA_PLACEHOLDER;

    document.getElementById('node-count').innerText = graphData.nodes.length;
    document.getElementById('edge-count').innerText = graphData.edges.length;

    const cy = cytoscape({
      container: document.getElementById('cy'),
      elements: [...graphData.nodes, ...graphData.edges],
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'color': '#f3f4f6',
            'font-size': '10px',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'background-color': function(ele) {
              const type = ele.data('type');
              if (type === 'Attested Computation') return '#ff5722';
              if (type === 'Scientific Model') return '#00e5ff';
              if (type === 'Architecture Document') return '#b388ff';
              if (type === 'Agent Role') return '#ffd600';
              if (type === 'Behavioral Rule') return '#ff1744';
              if (type === 'Directory Index') return '#78909c';
              return '#4caf50';
            },
            'border-width': 2,
            'border-color': function(ele) {
              const tier = ele.data('trust_tier');
              if (tier === 'Human-Reviewed') return '#00e676';
              if (tier === 'Machine-Confirmed') return '#00e5ff';
              return 'rgba(255,255,255,0.2)';
            },
            'width': 24,
            'height': 24
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.2,
            'line-color': 'rgba(255,255,255,0.18)',
            'target-arrow-color': 'rgba(255,255,255,0.25)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.6
          }
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#ffff00',
            'border-width': 4,
            'border-color': '#ffffff'
          }
        }
      ],
      layout: {
        name: 'cose',
        animate: false,
        padding: 50,
        nodeRepulsion: 4500,
        idealEdgeLength: 60
      }
    });

    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      const data = node.data();

      const panel = document.getElementById('details-panel');
      panel.innerHTML = `
        <div class="concept-card">
          <div class="concept-title">${data.label}</div>
          <div class="tag-list">
            <span class="tag">${data.type}</span>
            <span class="tag tier">${data.trust_tier}</span>
            <span class="tag">${data.status}</span>
          </div>
          <div class="concept-desc">${data.description || '<i>No description declared.</i>'}</div>
          <div class="meta-item"><b>Asset Path:</b> <code>${data.id}</code></div>
        </div>
      `;
    });

    document.getElementById('search').addEventListener('input', function(e) {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        cy.nodes().removeClass('highlighted');
        return;
      }
      cy.nodes().forEach(n => {
        const d = n.data();
        const match = d.label.toLowerCase().includes(q) ||
                      d.type.toLowerCase().includes(q) ||
                      d.id.toLowerCase().includes(q);
        if (match) {
          n.addClass('highlighted');
        } else {
          n.removeClass('highlighted');
        }
      });
    });
  </script>
</body>
</html>
"""


def main() -> None:
    """CLI generator for the interactive OKF knowledge graph visualizer."""
    parser = argparse.ArgumentParser(description="Generate interactive Cytoscape.js OKF knowledge graph HTML.")
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--out", default="docs/viz.html", help="Output HTML path (default: docs/viz.html)")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    out_path = Path(args.out).resolve()

    directories = ["docs", ".agents"]
    print(f"🕸️  Building knowledge graph from {directories}...")
    graph_data = build_graph_data(root_path, directories)

    print(f"📊 Extracted {len(graph_data['nodes'])} nodes and {len(graph_data['edges'])} edges.")

    html_content = HTML_TEMPLATE.replace("GRAPH_DATA_PLACEHOLDER", json.dumps(graph_data))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")

    print(f"✨ Standalone knowledge graph visualizer written to: {out_path.relative_to(root_path)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
