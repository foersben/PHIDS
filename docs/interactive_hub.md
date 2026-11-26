---
type: Tool
title: Interactive Architecture & Knowledge Graph Hub
status: stable
stale_after: "2027-06-01T00:00:00Z"
version: 1.1
description: Interactive visual exploration portal embedding the PHIDS system architecture visualizer and OKF v0.2 knowledge graph.
tags: [interactive, visualizer, architecture, okf, knowledge-graph, cytoscape]
generated: {by: process:docs-librarian, at: "2026-10-30T12:00:00Z"}
verified: {by: human:benjamin-foerster, at: "2026-11-26T02:32:00Z"}
---

# Interactive Architecture & Knowledge Graph Hub

Welcome to the **PHIDS Interactive Hub**. This portal embeds both the interactive full-stack simulation topology visualizer (`architecture_visualizer.html`) and the formal Open Knowledge Format (`OKF v0.2`) dependency network (`viz.html`).

<div class="metric-grid">
    <div class="metric-card">
        <div class="metric-header">Architecture Nodes</div>
        <div class="metric-value">26 Modules</div>
        <div class="metric-desc">4-column swimlanes tracing FastAPI ingress through ECS/Numba kernels to Zarr replay and DSE.</div>
    </div>
    <div class="metric-card">
        <div class="metric-header">Knowledge Graph</div>
        <div class="metric-value">OKF v0.2</div>
        <div class="metric-desc">Machine-attested semantic graph linking scientific models, ECS schemas, agent roles, and data-flow invariants.</div>
    </div>
    <div class="metric-card">
        <div class="metric-header">AST Verification</div>
        <div class="metric-value">Live Code</div>
        <div class="metric-desc">Frontmatter sources and claims bound directly to verified Python AST nodes and source line ranges.</div>
    </div>
</div>

---

## 1. Interactive System Architecture Visualizer

Explore the 4-layer PHIDS runtime topology (API/MCP, Loop orchestration, Data-Oriented ECS/Numba PDEs, and Zarr/Batch/DSE), compare empirical `64x32` to `256x256` grid scaling benchmarks, and tune interactive Softmax chemotaxis and Hill priming response sliders.

<div class="visualizer-wrapper" id="vis-arch-wrapper">
    <div class="visualizer-header">
        <div class="title">
            <span class="badge-tag success">Live Topology</span>
            PHIDS Full-Stack Architecture &amp; Dynamical Systems Visualizer
        </div>
        <div class="visualizer-actions">
            <button class="btn-fullscreen" data-target="vis-arch-wrapper" type="button"><i class="fa-solid fa-expand"></i> Fullscreen</button>
        </div>
    </div>
    <iframe class="visualizer-iframe" src="../architecture_visualizer.html" title="PHIDS Architecture Visualizer" allow="fullscreen"></iframe>
</div>

---

## 2. OKF v0.2 Knowledge Graph Explorer

The visualizer below renders the machine-attested knowledge graph compiled by `scripts/governance/visualize_okf.py` and validated by `scripts/governance/validate_okf.py`. Every node represents an audited concept document, technical specification, or agent skill, connected by verified semantic dependencies and code evidence.

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
    <iframe class="visualizer-iframe" src="../viz.html" title="OKF Knowledge Graph Explorer" allow="fullscreen"></iframe>
</div>

### Visualizer Features & Navigation Guide

* **Physics & Layout Controls:** Use the layout selector in each top toolbar to switch between:
  * **4-Column Swimlanes / Dagre LR:** Visualises left-to-right causal flows from UI/API ingress through simulation kernels to telemetry and DSE.
  * **Concentric Rings / Vertical TB:** Organises documentation nodes hierarchically by degree centrality, trust tiers, or vertical stage flow.
  * **CoSE Physics (OKF Graph):** Force-directed spring embedder clustering related concepts into spatial islands.
* **Domain & Layer Filter Chips:** Click the colour-coded chips in either canvas to isolate specific architectural layers or documentation domains.
* **Verified Code Claims & Inspector Drawers:** Selecting any node opens its slide-over drawer displaying repository paths, mathematical invariants rendered with KaTeX, trust/freshness metadata, and linked neighbourhood traversal.
* **Real-Time Substring Search:** Filter graph nodes dynamically by title, tag, file path, or architectural responsibility.
