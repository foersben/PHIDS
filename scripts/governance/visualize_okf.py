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
import importlib
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

try:
    from scripts.governance.validate_okf import resolve_ast_node_lines as _resolve_ast_node_lines
    from scripts.governance.visualize_okf_template import HTML_TEMPLATE
except ModuleNotFoundError:
    _resolve_ast_node_lines = importlib.import_module("validate_okf").resolve_ast_node_lines
    HTML_TEMPLATE = importlib.import_module("visualize_okf_template").HTML_TEMPLATE

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
        "src/phids/engine/systems/lifecycle/",
        "src/phids/engine/components/plant.py",
    ],
    "docs/scientific_model/part_2_autotrophic_dynamics/morphological_defenses.md": [
        "src/phids/engine/systems/interaction/",
        "src/phids/engine/systems/signaling/",
        "src/phids/engine/components/plant.py",
        "src/phids/engine/components/substances.py",
    ],
    "docs/scientific_model/part_3_signaling_and_transport/reaction_diffusion.md": [
        "src/phids/engine/core/diffusion.py",
        "src/phids/engine/systems/signaling/",
    ],
    "docs/scientific_model/part_3_signaling_and_transport/chemotaxis.md": [
        "src/phids/engine/core/flow/",
        "src/phids/engine/systems/interaction/movement/",
    ],
    "docs/scientific_model/part_4_heterotrophic_kinematics/herbivore_behavior.md": [
        "src/phids/engine/systems/interaction/",
        "src/phids/engine/components/swarm.py",
    ],
    "docs/scientific_model/part_4_heterotrophic_kinematics/population_dynamics.md": [
        "src/phids/engine/systems/interaction/population.py",
        "src/phids/engine/systems/lifecycle/reproduction.py",
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
    """Parse YAML frontmatter from markdown content if present."""
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


def _extract_fallback_claims(fm_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract claims from frontmatter sources if no external claims exist."""
    claims: list[dict[str, Any]] = []
    sources = fm_dict.get("sources")
    if not isinstance(sources, list):
        return claims

    for src_item in sources:
        if isinstance(src_item, dict) and "resource" in src_item:
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
        claims = _extract_fallback_claims(fm_dict)

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
