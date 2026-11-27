# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Standalone HTML/CSS/JS template for the interactive OKF knowledge graph visualizer."""

from __future__ import annotations

HTML_TEMPLATE: str = """<!DOCTYPE html>
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
