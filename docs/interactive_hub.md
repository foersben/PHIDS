---
type: Tool
title: Interactive Architecture & Knowledge Graph Hub
status: stable
stale_after: "2027-01-01T00:00:00Z"
version: 1.0
description: Interactive visual exploration portal embedding the PHIDS simulation architecture visualizer and OKF v0.2 knowledge graph.
tags: [interactive, visualizer, architecture, okf, knowledge-graph, cytoscape]
generated: {by: process:docs-librarian, at: "2026-10-30T12:00:00Z"}
verified: {by: process:docs-librarian, at: "2026-10-30T12:00:00Z"}
---

# Interactive Architecture & Knowledge Graph Hub

Welcome to the **PHIDS Interactive Hub**. This portal provides real-time, interactive graph visualizations of the data-oriented Entity Component System (ECS) architecture, spatiotemporal PDE reaction-diffusion fields, double-buffered execution pipelines, and the formal Open Knowledge Format (OKF v0.2) dependency network.

<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-header">Knowledge Graph</div>
        <div class="metric-value">OKF v0.2</div>
        <div class="metric-desc">Machine-attested semantic graph linking scientific models, ECS schemas, agent roles, and data-flow invariants.</div>
    </div>
    <div class="metric-card">
        <div class="metric-header">Graph Engine</div>
        <div class="metric-value">Cytoscape.js</div>
        <div class="metric-desc">Multi-layout topology canvas supporting Dagre LR, Concentric rings, and CoSE physics clustering.</div>
    </div>
    <div class="metric-card">
        <div class="metric-header">AST Verification</div>
        <div class="metric-value">Live Code</div>
        <div class="metric-desc">Frontmatter sources and claims bound directly to verified Python AST nodes and source line ranges.</div>
    </div>
</div>

---

## 1. OKF v0.2 Knowledge Graph Explorer

The visualizer below renders the machine-attested knowledge graph compiled by `scripts/governance/visualize_okf.py` and validated by `scripts/governance/validate_okf.py`. Every node represents an audited concept document, technical specification, or agent workflow, connected by verified semantic dependencies and code evidence.

<div class="visualizer-wrapper" id="vis-okf-wrapper">
    <div class="visualizer-header">
        <div class="title">
            <span class="badge-tag success">Verified OKF v0.2</span>
            Open Knowledge Graph &amp; Agentic Governance Explorer
        </div>
        <div class="visualizer-actions">
            <button class="btn-fullscreen" data-target="vis-okf-wrapper" type="button"><i class="fa-solid fa-expand"></i> Fullscreen</button>
        </div>
    </div>
    <iframe class="visualizer-iframe" src="viz.html" title="OKF Knowledge Graph Explorer" allow="fullscreen"></iframe>
</div>

### Visualizer Features & Navigation Guide

* **Physics & Layout Controls:** Use the layout selector in the top toolbar to switch between:
    * **Hierarchical (Dagre LR):** Visualises clear left-to-right causal flows from foundational models to runtime systems.
    * **Concentric Rings:** Organises documentation nodes hierarchically by degree centrality and trust tiers.
    * **CoSE Physics:** Force-directed spring embedder clustering closely related concepts into spatial islands.
* **Domain Filter Chips:** Click the domain chips (*Docs & Architecture*, *Skills & Workflows*, *Agent Roles & Rules*, *OpenWiki & Claims*) to filter the active canvas in real time.
* **Verified Code Claims & AST Inspection:** Selecting any concept node opens the right-hand inspection drawer, displaying:
    * Frontmatter metadata: Trust Tier (§5.3), Freshness Status (§5.5), and Git provenance.
    * **Verified Code Evidence:** Direct links to primary Python source files and AST nodes (`c.file:c.lines`).
    * **Semantic Link Pills:** Interactive incoming and outgoing link chips allowing frictionless traversal across related documents.
* **Real-Time Substring Search:** Filter graph nodes dynamically by title, tag, file path, or concept summary.
