#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Interactive Cytoscape.js knowledge graph visualizer for OKF v0.2 bundles.

Generates a standalone, rich HTML file (`docs/viz.html`) that renders the complete
knowledge graph across `docs/`, `.agents/`, and `openwiki/`, with color-coded node types,
domain filter chips, Dagre LR / Concentric / CoSE layout switching, interactive search,
semantic incoming/outgoing link navigation, and verified code claim inspection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Ensure repository root is in sys.path when invoked directly as a script
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.governance.validate_okf import resolve_ast_node_lines as _resolve_ast_node_lines  # noqa: E402

# Claim files whose claims are shown on a doc node regardless of evidence files.
DOC_CLAIMS_MAPPING: dict[str, list[str]] = {
    "quickstart.json": ["docs/index.md"],
}

# Claim JSON files that are never copied onto docs/ nodes (they stay on their openwiki page only).
OPENWIKI_ONLY_CLAIM_FILES: frozenset[str] = frozenset({"testing/test-strategy-and-invariants.json"})

# Doc node -> repo path prefixes (trailing "/") or exact files its claims may cite as primary evidence.
DOC_FILE_COVERAGE: dict[str, list[str]] = {
    "docs/scientific_model/part_1_foundations/mathematical_framework.md": [
        "src/phids/engine/core/",
    ],
    "docs/scientific_model/part_1_foundations/wsn_isomorphism.md": [
        "src/phids/engine/core/",
    ],
    "docs/scientific_model/part_2_autotrophic_dynamics/flora_and_symbiosis.md": [
        "src/phids/engine/systems/flora/",
    ],
    "docs/scientific_model/part_2_autotrophic_dynamics/morphological_defenses.md": [
        "src/phids/engine/systems/defense/",
    ],
    "docs/scientific_model/part_3_signaling_and_transport/reaction_diffusion.md": [
        "src/phids/engine/core/diffusion.py",
        "src/phids/engine/systems/signaling/",
    ],
    "docs/scientific_model/part_3_signaling_and_transport/chemotaxis.md": [
        "src/phids/engine/systems/herbivore/",
    ],
    "docs/scientific_model/part_4_heterotrophic_kinematics/herbivore_behavior.md": [
        "src/phids/engine/systems/herbivore/",
    ],
    "docs/scientific_model/part_4_heterotrophic_kinematics/population_dynamics.md": [
        "src/phids/engine/systems/herbivore/",
    ],
    "docs/scientific_model/part_5_ecosystem_synthesis/ecological_analytics.md": [
        "src/phids/telemetry/",
    ],
    "docs/technical_architecture/system_architecture.md": [
        "src/phids/",
    ],
    "docs/technical_architecture/engine_execution.md": [
        "src/phids/engine/core/",
    ],
    "docs/technical_architecture/interfaces_and_ui.md": [
        "src/phids/api/",
    ],
    "docs/technical_architecture/telemetry.md": [
        "src/phids/telemetry/",
    ],
    "docs/technical_architecture/testing_architecture.md": [
        "tests/",
    ],
    "docs/technical_architecture/signaling_triggers.md": [
        "src/phids/engine/systems/signaling/",
    ],
    "docs/reference/api.md": [
        "src/phids/api/",
    ],
    "docs/reference/module-map.md": [
        "src/phids/",
    ],
}

MD_LINK_RE = re.compile(r"\]\(([^:\s#)]+)(?:#[^)]+)?\)")
MERMAID_CLICK_RE = re.compile(r'click\s+\w+\s+"([^"\s#]+)(?:#[^"]+)?"')
BACKTICK_RE = re.compile(r"`([^`]+\.md)`")


def _extract_trust_tier(verified: Any, rel_id: str = "") -> str:
    """Determine trust tier from OKF verified metadata, assigning Machine-Confirmed to repository indices."""
    if not verified:
        if rel_id.startswith("openwiki/") or rel_id in (".agents/index.md", ".agents/log.md"):
            return "Machine-Confirmed"
        return "Unverified"
    v_list = [verified] if isinstance(verified, dict) else verified
    if any(isinstance(v, dict) and str(v.get("by", "")).startswith("human:") for v in v_list):
        return "Human-Reviewed"
    return "Machine-Confirmed"


def _determine_domain(rel_id: str) -> str:
    """Classify document into one of the four UI domains."""
    if rel_id.startswith("openwiki/"):
        return "OpenWiki & Claims"
    if rel_id.startswith((".agents/skills/", ".agents/workflows/")):
        return "Skills & Workflows"
    if rel_id.startswith(".agents/"):
        return "Agent Roles & Rules"
    return "Docs & Architecture"


GENERIC_HEADINGS: set[str] = {"files", "directories", "mandates", "directives"}


def _extract_h1_title(content: str) -> str | None:
    """Find the first level-1 markdown heading (# Heading), ignoring subheadings and generic titles."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("##"):
            title = line[2:].strip()
            if title and title.lower() not in GENERIC_HEADINGS:
                return title
    return None


def _extract_first_paragraph(content: str) -> str:
    """Return the first prose paragraph following the first #  heading (frontmatter-free documents)."""
    lines = content.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
    if start is None:
        return ""
    buf: list[str] = []
    for ln in lines[start + 1 :]:
        stripped = ln.strip()
        if not stripped:
            if buf:
                break
            continue
        if stripped.startswith(("#", "```", "|", "<", "---")) and not buf:
            continue
        if stripped.startswith(("#", "```", "|")):
            break
        buf.append(stripped)
    return " ".join(buf)


def _format_stem_title(stem: str) -> str:
    """Format file stem into human-readable title."""
    clean = re.sub(r"^\d+-", "", stem)
    return clean.replace("_", " ").replace("-", " ").title()


def _derive_index_title(rel_id: str) -> str:
    """Derive clean descriptive title for directory index files lacking explicit title."""
    if rel_id == "openwiki/index.md":
        return "OpenWiki Root Index"
    if rel_id.startswith("openwiki/") and rel_id.endswith("/index.md"):
        subdir = rel_id[len("openwiki/") : -len("/index.md")].strip("/")
        return f"OpenWiki: {subdir.title()} Index"
    if rel_id == ".agents/index.md":
        return "Agent Ecosystem Index"
    if rel_id.endswith("/index.md"):
        parent_dir = Path(rel_id).parent.name
        return f"{_format_stem_title(parent_dir)} Index"
    return _format_stem_title(Path(rel_id).stem)


def _resolve_node_title(fm_title: str | None, content: str, rel_id: str, file_path: Path) -> str:
    """Resolve node title using (1) frontmatter, (2) # H1, (3) index derivation, (4) filename stem."""
    if fm_title and fm_title.strip():
        return fm_title.strip()
    h1 = _extract_h1_title(content)
    if h1:
        return h1
    if rel_id.endswith("/index.md") or rel_id == "index.md":
        return _derive_index_title(rel_id)
    return _format_stem_title(file_path.stem)


def _determine_node_type(rel_id: str, fm_type: str | None) -> str:
    """Determine OKF node type with normalization."""
    if fm_type and fm_type.strip():
        raw = fm_type.strip()
        norm_map = {
            "architecture": "Architecture",
            "concept": "Concept",
            "guide": "Guide",
            "workflow": "Workflow",
            "operations": "Reference",
            "service": "Reference",
            "testing": "Reference",
            "documentation": "Reference",
        }
        return norm_map.get(raw.lower(), raw.title() if raw.islower() else raw)
    if rel_id.endswith("/index.md") or rel_id == "index.md":
        return "Directory Index"
    if ".agents/roles/" in rel_id:
        return "Agent Role"
    if ".agents/rules/" in rel_id:
        return "Agent Rule"
    if ".agents/workflows/" in rel_id:
        return "Workflow"
    if ".agents/skills/" in rel_id:
        return "Agent Skill"
    if rel_id.startswith("openwiki/"):
        return "OpenWiki"
    return "Concept"


def _compute_portal_url(rel_id: str) -> str | None:
    """Compute relative Zensical portal URL for docs pages."""
    if not rel_id.startswith("docs/"):
        return None
    sub = rel_id[len("docs/") :]
    if sub == "index.md":
        return "./"
    if sub.endswith("/index.md"):
        return f"./{sub[: -len('/index.md')]}/"
    if sub.endswith(".md"):
        return f"./{sub[: -len('.md')]}/"
    return f"./{sub}"


def _parse_claim_evidence(resource: str) -> tuple[str, str]:
    """Parse repo:// resource into (file, lines)."""
    clean = resource.replace("repo://", "").strip()
    if "#" in clean:
        parts = clean.split("#", 1)
        return parts[0], parts[1]
    return clean, ""


def _parse_claim_entry(c: dict[str, Any], root_path: Path) -> dict[str, Any]:
    """Convert raw claim dict into structured claim object, resolving ast_target to live lines."""
    stmt = c.get("statement", "").strip()
    ev_list = c.get("evidence", [])
    primary_file, primary_lines = "", ""
    if ev_list:
        primary_file, primary_lines = _parse_claim_evidence(ev_list[0].get("resource", ""))
    ast_target = str(c.get("ast_target", ""))
    if ast_target and primary_file.endswith(".py"):
        bounds = _resolve_ast_node_lines(root_path / primary_file, ast_target)
        if bounds:
            primary_lines = f"L{bounds[0]}-L{bounds[1]}"
    return {
        "claim": stmt,
        "file": primary_file,
        "lines": primary_lines,
        "ast_target": ast_target,
    }


def _matches_coverage(file: str, prefixes: list[str]) -> bool:
    """Return True when file equals a coverage entry or sits under a directory prefix."""
    return any(file == pre or (pre.endswith("/") and file.startswith(pre)) for pre in prefixes)


def _map_claims_to_nodes(
    rel_key: str,
    parsed_items: list[dict[str, Any]],
    node_claims: dict[str, list[dict[str, Any]]],
) -> None:
    """Map parsed claim items to openwiki and docs nodes."""
    openwiki_target = f"openwiki/{rel_key[:-5]}.md"
    node_claims.setdefault(openwiki_target, []).extend(parsed_items)

    for doc_target in DOC_CLAIMS_MAPPING.get(rel_key, []):
        node_claims.setdefault(doc_target, []).extend(parsed_items)

    if rel_key in OPENWIKI_ONLY_CLAIM_FILES:
        return

    for doc_target, prefixes in DOC_FILE_COVERAGE.items():
        matched = [item for item in parsed_items if _matches_coverage(item["file"], prefixes)]
        node_claims.setdefault(doc_target, []).extend(matched)


def _load_claims_data(root_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Parse openwiki/.claims/**/*.json and map claims to openwiki and docs nodes by file coverage."""
    claims_dir = root_path / "openwiki" / ".claims"
    node_claims: dict[str, list[dict[str, Any]]] = {}
    if not claims_dir.exists():
        return node_claims

    for json_file in sorted(claims_dir.rglob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        claims_list = data.get("claims", [])
        if not claims_list:
            continue

        rel_key = json_file.relative_to(claims_dir).as_posix()
        parsed_items = [_parse_claim_entry(c, root_path) for c in claims_list]
        _map_claims_to_nodes(rel_key, parsed_items, node_claims)

    return {k: v for k, v in node_claims.items() if v}


def _resolve_relative_candidate(cand: Path, root_path: Path, node_ids: set[str]) -> str | None:
    """Check if candidate path is a recognized graph node."""
    if cand.is_file():
        try:
            rel = cand.resolve().relative_to(root_path).as_posix()
            if rel in node_ids:
                return rel
        except ValueError:
            pass
    return None


def _resolve_target_path(
    link_str: str,
    src_file: Path,
    root_path: Path,
    node_ids: set[str],
) -> str | None:
    """Resolve link, zensical directory, or backticked target to a known node ID."""
    if link_str.startswith(("http://", "https://", "mailto:", "#")):
        return None
    link_clean = link_str.split("#")[0].split("?")[0].strip()
    if not link_clean:
        return None

    resolved = _resolve_relative_candidate(src_file.parent / link_clean, root_path, node_ids)
    if resolved:
        return resolved

    resolved = _resolve_relative_candidate(root_path / link_clean.lstrip("/"), root_path, node_ids)
    if resolved:
        return resolved

    clean_dir = link_clean.strip("/")
    for cand in [
        root_path / f"docs/{clean_dir}.md",
        root_path / f"docs/{clean_dir}/index.md",
        src_file.parent / f"{clean_dir}.md",
        src_file.parent / f"{clean_dir}/index.md",
    ]:
        resolved = _resolve_relative_candidate(cand, root_path, node_ids)
        if resolved:
            return resolved

    return None


def _extract_content_links(
    content: str,
    src_file: Path,
    root_path: Path,
    node_ids: set[str],
) -> set[str]:
    """Extract semantic links from markdown syntax, Mermaid clicks, and backticked files."""
    targets: set[str] = set()
    for link_str in MD_LINK_RE.findall(content):
        t = _resolve_target_path(link_str, src_file, root_path, node_ids)
        if t:
            targets.add(t)

    for link_str in MERMAID_CLICK_RE.findall(content):
        t = _resolve_target_path(link_str, src_file, root_path, node_ids)
        if t:
            targets.add(t)

    for link_str in BACKTICK_RE.findall(content):
        t = _resolve_target_path(link_str, src_file, root_path, node_ids)
        if t:
            targets.add(t)

    return targets


def _extract_item_link(
    item: Any,
    src_file: Path,
    root_path: Path,
    node_ids: set[str],
) -> str | None:
    """Resolve a single frontmatter list item to a target node ID."""
    if isinstance(item, str):
        return _resolve_target_path(item, src_file, root_path, node_ids)
    if isinstance(item, dict) and "resource" in item:
        clean = str(item["resource"]).replace("repo://", "")
        return _resolve_target_path(clean, src_file, root_path, node_ids)
    return None


def _extract_frontmatter_links(
    fm: dict[str, Any],
    src_file: Path,
    root_path: Path,
    node_ids: set[str],
) -> set[str]:
    """Extract links from depends_on, related, and sources in frontmatter."""
    targets: set[str] = set()
    for key in ("depends_on", "related", "sources"):
        val = fm.get(key)
        if isinstance(val, list):
            for item in val:
                t = _extract_item_link(item, src_file, root_path, node_ids)
                if t:
                    targets.add(t)
    return targets


def _link_directory_indices(files: list[Path], root_path: Path) -> set[tuple[str, str]]:
    """Connect each index.md to sibling member files in the same directory."""
    edges: set[tuple[str, str]] = set()
    for f in files:
        if f.name == "index.md":
            src_id = f.relative_to(root_path).as_posix()
            dir_path = f.parent
            for other in files:
                other_id = other.relative_to(root_path).as_posix()
                if other_id != src_id and other.parent == dir_path:
                    edges.add((src_id, other_id))
    return edges


def _link_section_hubs(node_ids: set[str]) -> set[tuple[str, str]]:
    """Connect root docs/index.md to section indices and agent/wiki hubs."""
    edges: set[tuple[str, str]] = set()
    if "docs/index.md" not in node_ids:
        return edges

    for nid in node_ids:
        if nid.startswith("docs/") and nid.endswith("/index.md") and nid != "docs/index.md":
            edges.add(("docs/index.md", nid))

    for hub in ("openwiki/index.md", ".agents/AGENTS.md", ".agents/index.md"):
        if hub in node_ids:
            edges.add(("docs/index.md", hub))

    return edges


def _link_domain_roots(node_ids: set[str]) -> set[tuple[str, str]]:
    """Connect agent routing file and openwiki index to their respective domain children."""
    edges: set[tuple[str, str]] = set()
    if ".agents/AGENTS.md" in node_ids:
        for nid in node_ids:
            if nid.startswith(".agents/") and nid != ".agents/AGENTS.md":
                edges.add((".agents/AGENTS.md", nid))

    if "openwiki/index.md" in node_ids:
        for nid in node_ids:
            if nid.startswith("openwiki/") and nid != "openwiki/index.md":
                edges.add(("openwiki/index.md", nid))

    return edges


def _build_structural_edges(
    files: list[Path],
    root_path: Path,
    node_ids: set[str],
) -> set[tuple[str, str]]:
    """Build structural hierarchy connections ensuring zero orphan nodes."""
    return _link_directory_indices(files, root_path) | _link_section_hubs(node_ids) | _link_domain_roots(node_ids)


def _collect_markdown_files(root_path: Path, directories: list[str]) -> list[Path]:
    """Collect valid markdown files across target directories, excluding archive/site files."""
    files: list[Path] = []
    for dir_name in directories:
        dir_path = root_path / dir_name
        if not dir_path.exists():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            file_posix = md_file.as_posix()
            if "docs/.archive/" not in file_posix and "site/" not in file_posix:
                files.append(md_file)
    return files


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        loaded = yaml.safe_load(parts[1])
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return {}


def _extract_source_claims(fm_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract claims from 'sources' listed in frontmatter."""
    claims: list[dict[str, Any]] = []
    if "sources" not in fm_dict or not isinstance(fm_dict["sources"], list):
        return claims

    for src_item in fm_dict["sources"]:
        if not isinstance(src_item, dict) or "resource" not in src_item:
            continue
        res_path = str(src_item["resource"]).replace("repo://", "").strip()
        claims.append(
            {
                "claim": f"Verified OKF resource link: {src_item.get('id', res_path)}",
                "file": res_path,
                "lines": "",
                "ast_target": "",
            }
        )
    return claims


def _extract_doc_metadata(
    f: Path,
    root_path: Path,
    claims_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Extract frontmatter and attributes for a single markdown file."""
    rel_id = f.relative_to(root_path).as_posix()
    content = f.read_text(encoding="utf-8")
    fm_dict = _parse_frontmatter(content)

    title = _resolve_node_title(fm_dict.get("title"), content, rel_id, f)
    node_type = _determine_node_type(rel_id, fm_dict.get("type"))
    domain = _determine_domain(rel_id)
    trust_tier = _extract_trust_tier(fm_dict.get("verified"), rel_id)
    status = str(fm_dict.get("status", "stable"))
    version = str(fm_dict.get("version", "1.0"))
    stale_after = str(fm_dict.get("stale_after", ""))
    description = str(fm_dict.get("description", "")) or _extract_first_paragraph(content)
    portal_url = _compute_portal_url(rel_id)

    claims = list(claims_map.get(rel_id, []))
    if not claims:
        claims.extend(_extract_source_claims(fm_dict))

    return {
        "id": rel_id,
        "title": title,
        "type": node_type,
        "domain": domain,
        "trust_tier": trust_tier,
        "status": status,
        "version": version,
        "stale_after": stale_after,
        "description": description,
        "claims": claims,
        "portal_url": portal_url,
        "github_url": f"https://github.com/foersben/PHIDS/blob/develop/{rel_id}",
        "raw_content": content,
        "fm_dict": fm_dict,
    }


def _collect_document_edges(
    meta: dict[str, Any],
    f: Path,
    root_path: Path,
    node_ids: set[str],
) -> set[tuple[str, str]]:
    """Collect semantic outgoing edges for a single document."""
    doc_edges: set[tuple[str, str]] = set()
    src_id = meta["id"]
    for t in _extract_content_links(meta["raw_content"], f, root_path, node_ids):
        if t != src_id:
            doc_edges.add((src_id, t))
    for t in _extract_frontmatter_links(meta["fm_dict"], f, root_path, node_ids):
        if t != src_id:
            doc_edges.add((src_id, t))
    return doc_edges


def _build_all_edges(
    files: list[Path],
    doc_meta_list: list[dict[str, Any]],
    root_path: Path,
    node_ids: set[str],
) -> set[tuple[str, str]]:
    """Build all structural and semantic edges across documents."""
    edges_set = set(_build_structural_edges(files, root_path, node_ids))
    for meta, f in zip(doc_meta_list, files, strict=True):
        edges_set |= _collect_document_edges(meta, f, root_path, node_ids)
    return edges_set


def _format_node_element(m: dict[str, Any]) -> dict[str, Any]:
    """Format single node dictionary for Cytoscape.js payload."""
    return {
        "data": {
            "id": m["id"],
            "label": m["title"],
            "type": m["type"],
            "domain": m["domain"],
            "trust_tier": m["trust_tier"],
            "status": m["status"],
            "version": m["version"],
            "stale_after": m["stale_after"],
            "description": m["description"],
            "claims": m["claims"],
            "portal_url": m["portal_url"],
            "github_url": m["github_url"],
        }
    }


def _format_edge_element(src: str, tgt: str) -> dict[str, Any]:
    """Format single edge dictionary for Cytoscape.js payload."""
    return {
        "data": {
            "id": f"{src}->{tgt}",
            "source": src,
            "target": tgt,
        }
    }


def build_graph_data(root_path: Path, directories: list[str]) -> dict[str, Any]:
    """Construct complete node and edge payloads for the Cytoscape graph."""
    files = _collect_markdown_files(root_path, directories)
    node_ids = {f.relative_to(root_path).as_posix() for f in files}
    claims_map = _load_claims_data(root_path)

    doc_meta_list = [_extract_doc_metadata(f, root_path, claims_map) for f in files]
    edges_set = _build_all_edges(files, doc_meta_list, root_path, node_ids)

    nodes = [_format_node_element(m) for m in doc_meta_list]
    edges = [_format_edge_element(src, tgt) for src, tgt in sorted(edges_set)]

    return {"nodes": nodes, "edges": edges}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TaxonVision-MLOps Knowledge Graph (OKF v0.2)</title>
  <!-- Dependencies: Cytoscape, Dagre, Cytoscape-Dagre, Marked, FontAwesome -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <style>
    :root {
      --bg-color: #0b0f19;
      --card-bg: rgba(17, 24, 39, 0.90);
      --card-inner: rgba(255, 255, 255, 0.04);
      --border-color: rgba(255, 255, 255, 0.12);
      --border-focus: #00e5ff;
      --text-main: #f3f4f6;
      --text-dim: #9ca3af;
      --text-muted: #6b7280;

      /* OKF Taxonomy Palette */
      --color-arch: #a855f7;      /* Architecture / System Pattern */
      --color-concept: #00e5ff;   /* Specification / Concept */
      --color-ref: #3b82f6;       /* Reference / Guide / Report */
      --color-tool: #10b981;      /* Tool / Directory Index */
      --color-role: #f59e0b;      /* Agent Role */
      --color-rule: #f43f5e;      /* Agent Rule */
      --color-skill: #ec4899;     /* Agent Skill / Workflow */
      --color-wiki: #14b8a6;      /* OpenWiki Pages */
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

    /* Main Container: Canvas + Top Toolbar */
    #main-container {
      flex: 1;
      height: 100%;
      position: relative;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    #toolbar {
      position: absolute;
      top: 14px;
      left: 14px;
      right: 14px;
      z-index: 20;
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 8px 14px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }

    .chip-group {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    .chip {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-color);
      color: var(--text-dim);
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .chip:hover {
      background: rgba(255, 255, 255, 0.12);
      color: #fff;
    }
    .chip.active {
      background: rgba(0, 229, 255, 0.2);
      border-color: var(--border-focus);
      color: #00e5ff;
      box-shadow: 0 0 12px rgba(0, 229, 255, 0.3);
    }

    .toolbar-spacer {
      flex: 1;
    }

    .toolbar-control-group {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .select-layout {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--border-color);
      color: #fff;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 0.8rem;
      outline: none;
      cursor: pointer;
    }
    .select-layout:focus {
      border-color: var(--border-focus);
    }

    .btn-action {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid var(--border-color);
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: background 0.2s;
    }
    .btn-action:hover {
      background: rgba(255, 255, 255, 0.16);
    }

    #cy {
      flex: 1;
      height: 100%;
      background: radial-gradient(circle at 40% 50%, #111827 0%, #030712 100%);
    }

    /* Floating Legend */
    #legend {
      position: absolute;
      bottom: 16px;
      left: 16px;
      z-index: 15;
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 10px 14px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.5);
      font-size: 0.72rem;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px 14px;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-dim);
    }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }

    /* Sidebar Inspector */
    #sidebar {
      width: 440px;
      height: 100%;
      background: var(--card-bg);
      backdrop-filter: blur(18px);
      border-left: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      padding: 22px 20px;
      z-index: 25;
      box-shadow: -6px 0 28px rgba(0,0,0,0.6);
      overflow: hidden;
    }

    .brand-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 4px;
    }
    .brand-icon {
      font-size: 1.4rem;
      color: var(--color-concept);
    }
    .header-title {
      font-size: 1.15rem;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }
    .header-sub {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-bottom: 14px;
    }

    .search-box {
      width: 100%;
      padding: 9px 12px;
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      color: #fff;
      font-size: 0.85rem;
      margin-bottom: 12px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-box:focus {
      border-color: var(--border-focus);
    }

    .stats-row {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
    }
    .stat-badge {
      flex: 1;
      padding: 7px;
      background: var(--card-inner);
      border-radius: 6px;
      text-align: center;
      font-size: 0.7rem;
      border: 1px solid var(--border-color);
      color: var(--text-dim);
    }
    .stat-badge strong {
      display: block;
      font-size: 1.05rem;
      color: var(--color-concept);
      font-weight: 700;
    }

    #details-panel {
      flex: 1;
      overflow-y: auto;
      padding-right: 4px;
    }
    #details-panel::-webkit-scrollbar {
      width: 5px;
    }
    #details-panel::-webkit-scrollbar-thumb {
      background: rgba(255,255,255,0.15);
      border-radius: 4px;
    }

    .empty-state {
      font-size: 0.82rem;
      color: var(--text-muted);
      text-align: center;
      margin-top: 60px;
      line-height: 1.5;
    }
    .empty-state i {
      font-size: 2rem;
      display: block;
      margin-bottom: 12px;
      color: rgba(255,255,255,0.15);
    }

    .node-header {
      margin-bottom: 12px;
    }
    .node-domain-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 3px 8px;
      border-radius: 4px;
      background: rgba(255,255,255,0.06);
      color: var(--color-concept);
      margin-bottom: 6px;
      border: 1px solid rgba(255,255,255,0.1);
    }
    .node-title {
      font-size: 1.2rem;
      font-weight: 700;
      color: #fff;
      line-height: 1.3;
    }

    .meta-badges-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 14px;
    }
    .meta-pill {
      font-size: 0.7rem;
      padding: 3px 8px;
      border-radius: 12px;
      background: rgba(255,255,255,0.06);
      color: var(--text-dim);
      border: 1px solid var(--border-color);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .meta-pill.tier-human {
      background: rgba(0, 230, 118, 0.15);
      color: #00e676;
      border-color: rgba(0, 230, 118, 0.35);
    }
    .meta-pill.tier-machine {
      background: rgba(0, 229, 255, 0.15);
      color: #00e5ff;
      border-color: rgba(0, 229, 255, 0.35);
    }
    .meta-pill.type-badge {
      font-weight: 600;
    }

    .action-buttons {
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
    }
    .btn-link {
      flex: 1;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 7px 12px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
    }
    .btn-link-portal {
      background: rgba(0, 229, 255, 0.15);
      color: #00e5ff;
      border: 1px solid rgba(0, 229, 255, 0.35);
    }
    .btn-link-portal:hover {
      background: rgba(0, 229, 255, 0.25);
    }
    .btn-link-github {
      background: rgba(255, 255, 255, 0.06);
      color: #fff;
      border: 1px solid var(--border-color);
    }
    .btn-link-github:hover {
      background: rgba(255, 255, 255, 0.12);
    }

    .desc-box {
      font-size: 0.82rem;
      line-height: 1.45;
      color: #d1d5db;
      background: var(--card-inner);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 14px;
    }

    .asset-path-box {
      font-size: 0.72rem;
      color: var(--text-dim);
      margin-bottom: 14px;
      word-break: break-all;
    }
    .asset-path-box code {
      color: #e5e7eb;
      background: rgba(255,255,255,0.06);
      padding: 2px 5px;
      border-radius: 4px;
    }

    .section-title {
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-dim);
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .link-pills {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 14px;
    }
    .link-pill {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 10px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      font-size: 0.75rem;
      color: #e5e7eb;
      cursor: pointer;
      transition: all 0.15s;
    }
    .link-pill:hover {
      background: rgba(0, 229, 255, 0.15);
      border-color: var(--border-focus);
      color: #00e5ff;
    }
    .link-pill .type-tag {
      font-size: 0.65rem;
      color: var(--text-dim);
    }

    /* Claims Container */
    .claims-container {
      margin-top: 10px;
    }
    .claim-card {
      background: rgba(20, 184, 166, 0.08);
      border: 1px solid rgba(20, 184, 166, 0.25);
      border-radius: 6px;
      padding: 9px 11px;
      margin-bottom: 8px;
      font-size: 0.75rem;
    }
    .claim-statement {
      color: #e5e7eb;
      line-height: 1.35;
      margin-bottom: 6px;
    }
    .claim-evidence-tag {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.68rem;
      color: #2dd4bf;
      background: rgba(20, 184, 166, 0.15);
      padding: 2px 7px;
      border-radius: 4px;
      font-family: monospace;
    }
  </style>
</head>
<body>
  <div id="main-container">
    <div id="toolbar">
      <div class="chip-group">
        <button class="chip active" data-domain="all">
          <i class="fa-solid fa-layer-group"></i> All (<span id="chip-count-all">0</span>)
        </button>
        <button class="chip" data-domain="Docs & Architecture">
          <i class="fa-solid fa-book"></i> Docs & Architecture (<span id="chip-count-docs">0</span>)
        </button>
        <button class="chip" data-domain="OpenWiki & Claims">
          <i class="fa-solid fa-fingerprint"></i> OpenWiki & Claims (<span id="chip-count-wiki">0</span>)
        </button>
        <button class="chip" data-domain="Agent Roles & Rules">
          <i class="fa-solid fa-robot"></i> Roles & Rules (<span id="chip-count-roles">0</span>)
        </button>
        <button class="chip" data-domain="Skills & Workflows">
          <i class="fa-solid fa-diagram-project"></i> Skills & Workflows (<span id="chip-count-skills">0</span>)
        </button>
      </div>

      <div class="toolbar-spacer"></div>

      <div class="toolbar-control-group">
        <select id="layout-select" class="select-layout">
          <option value="dagre" selected>Hierarchical DAG (Dagre LR)</option>
          <option value="concentric">Concentric Hub</option>
          <option value="cose">Force-Directed (CoSE)</option>
        </select>
        <button id="btn-fit" class="btn-action" title="Fit to View">
          <i class="fa-solid fa-expand"></i> Fit
        </button>
      </div>
    </div>

    <div id="cy"></div>

    <div id="legend">
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-arch)"></span> Architecture / System Pattern</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-concept)"></span> Specification / Concept</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-ref)"></span> Reference / Guide / Report</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-tool)"></span> Tool / Directory Index</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-role)"></span> Agent Role</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-rule)"></span> Agent Rule</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-skill)"></span> Agent Skill / Workflow</div>
      <div class="legend-item"><span class="legend-dot" style="background:var(--color-wiki)"></span> OpenWiki (Cryptographic Claims)</div>
    </div>
  </div>

  <div id="sidebar">
    <div class="brand-row">
      <i class="fa-solid fa-circle-nodes brand-icon"></i>
      <div>
        <div class="header-title">TaxonVision-MLOps Knowledge Graph</div>
        <div class="header-sub">Open Knowledge Format (OKF v0.2) Explorer</div>
      </div>
    </div>

    <input type="text" id="search" class="search-box" placeholder="Search concepts, types, rules, paths..." />

    <div class="stats-row">
      <div class="stat-badge"><strong id="node-count">0</strong>Nodes</div>
      <div class="stat-badge"><strong id="edge-count">0</strong>Edges</div>
      <div class="stat-badge"><strong id="claims-count">0</strong>Claims</div>
    </div>

    <div id="details-panel">
      <div class="empty-state">
        <i class="fa-solid fa-hand-pointer"></i>
        Click any node in the knowledge graph to inspect its OKF frontmatter, trust tier, semantic links, and verified code claims.
      </div>
    </div>
  </div>

  <script>
    const graphData = GRAPH_DATA_PLACEHOLDER;

    // Type Color Resolver
    function getNodeColor(data) {
      if (data.domain === 'OpenWiki & Claims' || data.id.startsWith('openwiki/')) {
        return '#14b8a6';
      }
      const t = data.type;
      if (t === 'Architecture' || t === 'System Pattern') return '#a855f7';
      if (t === 'Specification' || t === 'Concept') return '#00e5ff';
      if (t === 'Reference' || t === 'Guide' || t === 'Report' || t === 'Documentation') return '#3b82f6';
      if (t === 'Tool' || t === 'Directory Index') return '#10b981';
      if (t === 'Agent Role') return '#f59e0b';
      if (t === 'Agent Rule') return '#f43f5e';
      if (t === 'Agent Skill' || t === 'Workflow') return '#ec4899';
      return '#3b82f6';
    }

    // Populate Counts
    const uniqueClaimKeys = new Set();
    graphData.nodes.forEach(n => (n.data.claims || []).forEach(c => uniqueClaimKeys.add(`${c.file}#${c.ast_target || ''}#${c.claim}`)));
    const totalClaims = uniqueClaimKeys.size;
    document.getElementById('node-count').innerText = graphData.nodes.length;
    document.getElementById('edge-count').innerText = graphData.edges.length;
    document.getElementById('claims-count').innerText = totalClaims;

    // Filter Chip Counts
    const counts = { all: graphData.nodes.length, docs: 0, wiki: 0, roles: 0, skills: 0 };
    graphData.nodes.forEach(n => {
      const d = n.data.domain;
      if (d === 'Docs & Architecture') counts.docs++;
      else if (d === 'OpenWiki & Claims') counts.wiki++;
      else if (d === 'Agent Roles & Rules') counts.roles++;
      else if (d === 'Skills & Workflows') counts.skills++;
    });
    document.getElementById('chip-count-all').innerText = counts.all;
    document.getElementById('chip-count-docs').innerText = counts.docs;
    document.getElementById('chip-count-wiki').innerText = counts.wiki;
    document.getElementById('chip-count-roles').innerText = counts.roles;
    document.getElementById('chip-count-skills').innerText = counts.skills;

    // Initialize Cytoscape
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
            'text-margin-y': 5,
            'background-color': function(ele) { return getNodeColor(ele.data()); },
            'border-width': 2,
            'border-color': function(ele) {
              const tier = ele.data('trust_tier');
              if (tier === 'Human-Reviewed') return '#00e676';
              if (tier === 'Machine-Confirmed') return '#00e5ff';
              return 'rgba(255,255,255,0.2)';
            },
            'width': function(ele) {
              const t = ele.data('type');
              if (t === 'Directory Index' || ele.data('id') === '.agents/AGENTS.md') return 34;
              return 24;
            },
            'height': function(ele) {
              const t = ele.data('type');
              if (t === 'Directory Index' || ele.data('id') === '.agents/AGENTS.md') return 34;
              return 24;
            },
            'transition-property': 'background-color, border-color, width, height, opacity',
            'transition-duration': '0.2s'
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.4,
            'line-color': 'rgba(255,255,255,0.20)',
            'target-arrow-color': 'rgba(255,255,255,0.30)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#ffffff',
            'shadow-blur': 20,
            'shadow-color': '#00e5ff',
            'shadow-opacity': 0.8,
            'shadow-offset-x': 0,
            'shadow-offset-y': 0
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'width': 2.5,
            'line-color': '#00e5ff',
            'target-arrow-color': '#00e5ff'
          }
        },
        {
          selector: '.search-match',
          style: {
            'border-width': 4,
            'border-color': '#ffd600',
            'width': 30,
            'height': 30
          }
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.15
          }
        }
      ],
      layout: {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 40,
        rankSep: 110,
        padding: 40
      }
    });

    // Layout Switcher
    function runLayout(layoutName) {
      let layoutConfig = {};
      if (layoutName === 'dagre') {
        layoutConfig = { name: 'dagre', rankDir: 'LR', nodeSep: 40, rankSep: 110, padding: 40 };
      } else if (layoutName === 'concentric') {
        layoutConfig = {
          name: 'concentric',
          concentric: function(node) { return node.degree(); },
          levelWidth: function() { return 2; },
          padding: 50
        };
      } else {
        layoutConfig = {
          name: 'cose',
          animate: false,
          padding: 50,
          nodeRepulsion: 7500,
          idealEdgeLength: 80
        };
      }
      cy.layout(layoutConfig).run();
    }

    document.getElementById('layout-select').addEventListener('change', function(e) {
      runLayout(e.target.value);
    });

    document.getElementById('btn-fit').addEventListener('click', function() {
      cy.fit(null, 40);
    });

    // Domain Filtering
    let activeDomain = 'all';
    document.querySelectorAll('.chip').forEach(btn => {
      btn.addEventListener('click', function() {
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        this.classList.add('active');
        activeDomain = this.getAttribute('data-domain');

        cy.batch(() => {
          if (activeDomain === 'all') {
            cy.elements().removeClass('faded');
          } else {
            cy.nodes().forEach(n => {
              if (n.data('domain') === activeDomain) {
                n.removeClass('faded');
              } else {
                n.addClass('faded');
              }
            });
            cy.edges().forEach(e => {
              if (!e.source().hasClass('faded') && !e.target().hasClass('faded')) {
                e.removeClass('faded');
              } else {
                e.addClass('faded');
              }
            });
          }
        });
      });
    });

    // Node Inspector
    function focusNode(nodeId) {
      const node = cy.getElementById(nodeId);
      if (node && node.length > 0) {
        cy.nodes().unselect();
        node.select();
        cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.0), duration: 350 });
        renderNodeInspector(node);
      }
    }

    function renderNodeInspector(node) {
      const d = node.data();
      const panel = document.getElementById('details-panel');

      const tierClass = d.trust_tier === 'Human-Reviewed' ? 'tier-human' : (d.trust_tier === 'Machine-Confirmed' ? 'tier-machine' : '');
      const typeColor = getNodeColor(d);

      // Outgoing & Incoming Edges
      const outEdges = node.outgoers('edge');
      const inEdges = node.incomers('edge');

      let outgoingHtml = '';
      if (outEdges.length > 0) {
        outgoingHtml = '<div class="section-title"><i class="fa-solid fa-arrow-right-from-bracket"></i> Outgoing Links (' + outEdges.length + ')</div><div class="link-pills">';
        outEdges.forEach(e => {
          const tgt = e.target();
          outgoingHtml += `<div class="link-pill" onclick="focusNode('${tgt.id()}')">
            <span>${tgt.data('label')}</span>
            <span class="type-tag">${tgt.data('type')}</span>
          </div>`;
        });
        outgoingHtml += '</div>';
      }

      let incomingHtml = '';
      if (inEdges.length > 0) {
        incomingHtml = '<div class="section-title"><i class="fa-solid fa-arrow-right-to-bracket"></i> Incoming Links (' + inEdges.length + ')</div><div class="link-pills">';
        inEdges.forEach(e => {
          const src = e.source();
          incomingHtml += `<div class="link-pill" onclick="focusNode('${src.id()}')">
            <span>${src.data('label')}</span>
            <span class="type-tag">${src.data('type')}</span>
          </div>`;
        });
        incomingHtml += '</div>';
      }

      // Claims List
      let claimsHtml = '';
      if (d.claims && d.claims.length > 0) {
        claimsHtml = `<div class="section-title"><i class="fa-solid fa-shield-halved" style="color:#14b8a6"></i> Verified Code Claims (${d.claims.length})</div><div class="claims-container">`;
        d.claims.forEach(c => {
          claimsHtml += `
            <div class="claim-card">
              <div class="claim-statement">${c.claim}</div>
              <div class="claim-evidence-tag">
                <i class="fa-solid fa-code"></i> ${c.file}${c.lines ? ':' + c.lines : ''}
              </div>
            </div>
          `;
        });
        claimsHtml += '</div>';
      }

      panel.innerHTML = `
        <div class="node-header">
          <div class="node-domain-badge"><i class="fa-solid fa-tag"></i> ${d.domain}</div>
          <div class="node-title">${d.label}</div>
        </div>

        <div class="meta-badges-row">
          <span class="meta-pill type-badge" style="color:${typeColor}; border-color:${typeColor}44; background:${typeColor}15">${d.type}</span>
          <span class="meta-pill ${tierClass}"><i class="fa-solid fa-certificate"></i> ${d.trust_tier}</span>
          <span class="meta-pill"><i class="fa-solid fa-clock"></i> ${d.status}</span>
          ${d.version ? `<span class="meta-pill">v${d.version}</span>` : ''}
        </div>

        <div class="action-buttons">
          ${d.portal_url ? `<a href="${d.portal_url}" target="_blank" class="btn-link btn-link-portal"><i class="fa-solid fa-book-open"></i> Open in Portal</a>` : ''}
          <a href="${d.github_url}" target="_blank" class="btn-link btn-link-github"><i class="fa-brands fa-github"></i> View Source</a>
        </div>

        <div class="desc-box">${d.description || '<i>No description declared in frontmatter.</i>'}</div>

        <div class="asset-path-box"><b>Asset Path:</b> <code>${d.id}</code></div>

        ${outgoingHtml}
        ${incomingHtml}
        ${claimsHtml}
      `;
    }

    cy.on('tap', 'node', function(evt) {
      renderNodeInspector(evt.target);
    });

    // Real-Time Search
    document.getElementById('search').addEventListener('input', function(e) {
      const q = e.target.value.toLowerCase().trim();
      cy.batch(() => {
        if (!q) {
          cy.nodes().removeClass('search-match');
          return;
        }
        cy.nodes().forEach(n => {
          const d = n.data();
          const match = d.label.toLowerCase().includes(q) ||
                        d.type.toLowerCase().includes(q) ||
                        d.id.toLowerCase().includes(q) ||
                        (d.description && d.description.toLowerCase().includes(q));
          if (match) {
            n.addClass('search-match');
          } else {
            n.removeClass('search-match');
          }
        });
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

    directories = ["docs", ".agents", "openwiki"]
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
