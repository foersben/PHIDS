/**
 * PHIDS Interactive Mermaid.js Controller
 * SPDX-FileCopyrightText: 2026 Benjamin Förster
 * SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
 *
 * Implements high-contrast responsive styling, palette observation,
 * pan, zoom, reset, and fullscreen viewports for Mermaid diagrams.
 */

function prepareMermaidBlocks() {
  const candidates = document.querySelectorAll("pre.mermaid, div.mermaid");

  for (const node of candidates) {
    if (node.dataset.mermaidPrepared === "true") {
      continue;
    }

    if (node.tagName === "PRE") {
      const code = node.querySelector("code");
      const text = code ? code.textContent ?? "" : node.textContent ?? "";
      const replacement = document.createElement("div");
      replacement.className = "mermaid";
      replacement.textContent = text;
      replacement.dataset.mermaidPrepared = "true";
      replacement.dataset.mermaidSource = text;
      node.replaceWith(replacement);
      continue;
    }

    if (!node.dataset.mermaidSource) {
      node.dataset.mermaidSource = node.textContent ?? "";
    }
    node.dataset.mermaidPrepared = "true";
  }
}

function ensureMermaidStyles() {
  if (document.getElementById("mermaid-custom-theme-style")) {
    return;
  }
  const style = document.createElement("style");
  style.id = "mermaid-custom-theme-style";
  style.textContent = `
    /* High-contrast crisp styling for all Mermaid diagrams */
    .mermaid svg {
      font-family: inherit !important;
      max-width: 100% !important;
      height: auto !important;
    }
    [data-md-color-scheme="slate"] .mermaid text {
      fill: #f8fafc !important;
    }
    [data-md-color-scheme="slate"] .mermaid .messageText {
      fill: #f8fafc !important;
      stroke: none !important;
    }
    [data-md-color-scheme="slate"] .mermaid .actor {
      stroke: #ff6e40 !important;
      fill: #1e2230 !important;
    }
    [data-md-color-scheme="slate"] .mermaid .actor-line {
      stroke: #94a3b8 !important;
    }
    [data-md-color-scheme="slate"] .mermaid .labelBox {
      stroke: #ff6e40 !important;
      fill: #1e2230 !important;
    }
    [data-md-color-scheme="slate"] .mermaid .labelText {
      fill: #f8fafc !important;
    }
    [data-md-color-scheme="slate"] .mermaid .loopText {
      fill: #f8fafc !important;
    }
    [data-md-color-scheme="slate"] .mermaid .node rect,
    [data-md-color-scheme="slate"] .mermaid .node circle,
    [data-md-color-scheme="slate"] .mermaid .node polygon {
      stroke: #ff6e40 !important;
      fill: #1e2230 !important;
    }
    [data-md-color-scheme="slate"] .mermaid .cluster rect {
      stroke: #ff6e40 !important;
      fill: #141824 !important;
    }
    [data-md-color-scheme="slate"] .mermaid .edgePath .path {
      stroke: #e2e8f0 !important;
      stroke-width: 1.5px !important;
    }
    [data-md-color-scheme="slate"] .mermaid .edgeLabel {
      background-color: #1e2230 !important;
      color: #f8fafc !important;
    }
    [data-md-color-scheme="slate"] .mermaid .edgeLabel rect {
      fill: #1e2230 !important;
      opacity: 0.85 !important;
    }
  `;
  document.head.appendChild(style);
}

function renderMermaidDiagrams() {
  if (typeof mermaid === "undefined") {
    return;
  }

  ensureMermaidStyles();
  const scheme = document.body ? document.body.getAttribute("data-md-color-scheme") : "slate";
  const isDark = scheme === "slate";

  prepareMermaidBlocks();

  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: isDark ? "dark" : "default",
    flowchart: {
      htmlLabels: true,
      curve: "basis",
      useMaxWidth: true,
    },
    sequence: {
      useMaxWidth: true,
      showSequenceNumbers: true,
      actorMargin: 50,
      boxMargin: 10,
      boxTextMargin: 5,
      noteMargin: 10,
      messageMargin: 35,
    },
    themeVariables: isDark
      ? {
          background: "transparent",
          primaryColor: "#1e2230",
          primaryTextColor: "#f8fafc",
          primaryBorderColor: "#ff6e40",
          secondaryColor: "#2a2d3d",
          secondaryTextColor: "#f8fafc",
          secondaryBorderColor: "#ff6e40",
          tertiaryColor: "#141824",
          tertiaryTextColor: "#f8fafc",
          tertiaryBorderColor: "#ff6e40",
          lineColor: "#e2e8f0",
          textColor: "#f8fafc",
          mainBkg: "#1e2230",
          errorBkgColor: "#7f1d1d",
          errorTextColor: "#fecaca",
          nodeBorder: "#ff6e40",
          nodeTextColor: "#f8fafc",
          clusterBkg: "#141824",
          clusterBorder: "#ff6e40",
          defaultLinkColor: "#e2e8f0",
          titleColor: "#ffcc80",
          edgeLabelBackground: "#1e2230",
          signalColor: "#e2e8f0",
          signalTextColor: "#f8fafc",
          actorBkg: "#1e2230",
          actorBorder: "#ff6e40",
          actorTextColor: "#f8fafc",
          actorLineColor: "#94a3b8",
          labelBoxBkgColor: "#1e2230",
          labelBoxBorderColor: "#ff6e40",
          labelTextColor: "#f8fafc",
          loopTextColor: "#f8fafc",
          noteBkgColor: "#2d221e",
          noteTextColor: "#ffcc80",
          noteBorderColor: "#ff6e40",
          activationBorderColor: "#ff6e40",
          activationBkgColor: "#374151",
          sequenceNumberColor: "#ffffff",
          classText: "#f8fafc",
          labelColor: "#f8fafc",
          altBackground: "#141824",
        }
      : {
          background: "transparent",
          primaryColor: "#f8fafc",
          primaryTextColor: "#0f172a",
          primaryBorderColor: "#ff6e40",
          secondaryColor: "#f1f5f9",
          secondaryTextColor: "#0f172a",
          secondaryBorderColor: "#ff6e40",
          tertiaryColor: "#ffffff",
          tertiaryTextColor: "#0f172a",
          tertiaryBorderColor: "#ff6e40",
          lineColor: "#334155",
          textColor: "#0f172a",
          mainBkg: "#ffffff",
          nodeBorder: "#ff6e40",
          nodeTextColor: "#0f172a",
          clusterBkg: "#f8fafc",
          clusterBorder: "#ff6e40",
          defaultLinkColor: "#334155",
          titleColor: "#c2410c",
          edgeLabelBackground: "#f8fafc",
          signalColor: "#1e293b",
          signalTextColor: "#0f172a",
          actorBkg: "#ffffff",
          actorBorder: "#ff6e40",
          actorTextColor: "#0f172a",
          actorLineColor: "#94a3b8",
          labelBoxBkgColor: "#ffffff",
          labelBoxBorderColor: "#ff6e40",
          labelTextColor: "#0f172a",
          loopTextColor: "#0f172a",
          noteBkgColor: "#fff7ed",
          noteTextColor: "#9a3412",
          noteBorderColor: "#ff6e40",
          activationBorderColor: "#ff6e40",
          activationBkgColor: "#e2e8f0",
          sequenceNumberColor: "#ffffff",
          classText: "#0f172a",
          labelColor: "#0f172a",
          altBackground: "#ffffff",
        },
  });

  const nodes = document.querySelectorAll("div.mermaid[data-mermaid-prepared='true']");
  if (nodes.length > 0) {
    try {
      const res = mermaid.run({ nodes });
      if (res && typeof res.then === "function") {
        res
          .then(() => {
            attachMermaidInteractivity();
          })
          .catch((err) => {
            console.warn("Mermaid execution warning:", err);
            attachMermaidInteractivity();
          });
      } else {
        attachMermaidInteractivity();
      }
    } catch (err) {
      console.warn("Mermaid execution error:", err);
      attachMermaidInteractivity();
    }
  } else {
    attachMermaidInteractivity();
  }
}

/**
 * Attaches interactive pan, zoom, reset, and fullscreen controls to all rendered Mermaid diagrams.
 */
function attachMermaidInteractivity() {
  const diagrams = document.querySelectorAll("div.mermaid");

  diagrams.forEach((container) => {
    const svg = container.querySelector("svg");
    if (!svg) {
      return;
    }

    // Check if container is already enhanced
    let wrapper = container.closest(".mermaid-interactive-wrapper");
    if (wrapper) {
      if (wrapper._mermaidController) {
        wrapper._mermaidController.resetView();
      }
      return;
    }

    // Construct interactive DOM hierarchy
    wrapper = document.createElement("div");
    wrapper.className = "mermaid-interactive-wrapper";

    const toolbar = document.createElement("div");
    toolbar.className = "mermaid-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", "Mermaid Diagram Display Controls");
    toolbar.innerHTML = `
      <button type="button" class="mermaid-tool-btn" data-action="zoom-in" title="Zoom in (+)" aria-label="Zoom in">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
      </button>
      <button type="button" class="mermaid-tool-btn" data-action="zoom-out" title="Zoom out (−)" aria-label="Zoom out">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>
      </button>
      <button type="button" class="mermaid-tool-btn" data-action="reset" title="Reset framing (↺)" aria-label="Reset view">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><polyline points="3 3 3 8 8 8"></polyline></svg>
      </button>
      <button type="button" class="mermaid-tool-btn" data-action="fullscreen" title="Toggle full screen (⛶)" aria-label="Toggle full screen">
        <svg class="icon-expand" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg>
        <svg class="icon-collapse" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="display:none;"><path d="M4 14h6m0 0v6m0-6-7 7m17-11h-6m0 0V4m0 6 7-7m-7 17v-6m0 0h6m-6 0 7 7M10 4v6m0 0H4m6 0L3 3"></path></svg>
      </button>
    `;

    const viewport = document.createElement("div");
    viewport.className = "mermaid-viewport";

    // Non-intrusive DOM placement: wrap container without disrupting flow
    container.parentNode.insertBefore(wrapper, container);
    viewport.appendChild(container);
    wrapper.appendChild(toolbar);
    wrapper.appendChild(viewport);

    // Subtle scroll hint to guide desktop users without trapping page scroll
    const hint = document.createElement("div");
    hint.className = "mermaid-scroll-hint";
    hint.textContent = "Use Ctrl + scroll to zoom";
    wrapper.appendChild(hint);

    let hintTimeout = null;
    function showScrollHint() {
      hint.classList.add("is-visible");
      if (hintTimeout) clearTimeout(hintTimeout);
      hintTimeout = setTimeout(() => {
        hint.classList.remove("is-visible");
      }, 1200);
    }

    // Viewport transform state
    let scale = 1.0;
    let pointX = 0;
    let pointY = 0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;

    function updateTransform() {
      container.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`;
      container.style.transformOrigin = "center center";
    }

    function resetView() {
      scale = 1.0;
      pointX = 0;
      pointY = 0;
      updateTransform();
    }

    // Mouse wheel zooming (unrestricted in fullscreen, gated by Ctrl/Meta inline)
    viewport.addEventListener("wheel", (e) => {
      const isFs = wrapper.classList.contains("is-fullscreen") || document.fullscreenElement === wrapper;
      if (!isFs && !e.ctrlKey && !e.metaKey) {
        showScrollHint();
        return;
      }

      e.preventDefault();
      viewport.classList.add("is-wheeling");

      const rect = viewport.getBoundingClientRect();
      const mouseX = e.clientX - rect.left - rect.width / 2;
      const mouseY = e.clientY - rect.top - rect.height / 2;

      const delta = e.deltaY < 0 ? 1.15 : 0.85;
      const newScale = Math.min(Math.max(0.2, scale * delta), 6.0);

      pointX = mouseX - (mouseX - pointX) * (newScale / scale);
      pointY = mouseY - (mouseY - pointY) * (newScale / scale);
      scale = newScale;

      updateTransform();

      clearTimeout(viewport._wheelTimer);
      viewport._wheelTimer = setTimeout(() => {
        viewport.classList.remove("is-wheeling");
      }, 150);
    }, { passive: false });

    // Pointer-based drag and pan
    viewport.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      if (e.target.closest("a, button, input")) return;

      isPanning = true;
      startX = e.clientX - pointX;
      startY = e.clientY - pointY;
      viewport.classList.add("is-dragging");
      viewport.setPointerCapture(e.pointerId);
    });

    viewport.addEventListener("pointermove", (e) => {
      if (!isPanning) return;
      pointX = e.clientX - startX;
      pointY = e.clientY - startY;
      updateTransform();
    });

    const stopPan = (e) => {
      if (!isPanning) return;
      isPanning = false;
      viewport.classList.remove("is-dragging");
      try {
        viewport.releasePointerCapture(e.pointerId);
      } catch (_) {}
    };

    viewport.addEventListener("pointerup", stopPan);
    viewport.addEventListener("pointercancel", stopPan);

    // Double-click resets view framing
    viewport.addEventListener("dblclick", (e) => {
      if (e.target.closest("a, button")) return;
      resetView();
    });

    function setFullscreenState(active) {
      const expandIcon = toolbar.querySelector(".icon-expand");
      const collapseIcon = toolbar.querySelector(".icon-collapse");

      if (active) {
        wrapper.classList.add("is-fullscreen");
        if (expandIcon) expandIcon.style.display = "none";
        if (collapseIcon) collapseIcon.style.display = "block";
      } else {
        wrapper.classList.remove("is-fullscreen");
        if (expandIcon) expandIcon.style.display = "block";
        if (collapseIcon) collapseIcon.style.display = "none";
      }
    }

    function toggleFullscreen() {
      const isCurrentlyFs =
        document.fullscreenElement === wrapper ||
        wrapper.classList.contains("is-fullscreen");

      if (isCurrentlyFs) {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        }
        setFullscreenState(false);
      } else {
        const req =
          wrapper.requestFullscreen ||
          wrapper.webkitRequestFullscreen ||
          wrapper.mozRequestFullScreen ||
          wrapper.msRequestFullscreen;

        if (req) {
          req.call(wrapper).then(() => {
            setFullscreenState(true);
          }).catch(() => {
            setFullscreenState(true);
          });
        } else {
          setFullscreenState(true);
        }
      }
    }

    // Button event routing
    toolbar.addEventListener("click", (e) => {
      const btn = e.target.closest(".mermaid-tool-btn");
      if (!btn) return;
      const action = btn.dataset.action;

      if (action === "zoom-in") {
        scale = Math.min(scale * 1.25, 6.0);
        updateTransform();
      } else if (action === "zoom-out") {
        scale = Math.max(scale * 0.8, 0.2);
        updateTransform();
      } else if (action === "reset") {
        resetView();
      } else if (action === "fullscreen") {
        toggleFullscreen();
      }
    });

    wrapper._mermaidController = {
      resetView,
      updateTransform,
      setFullscreenState,
    };
  });
}

// Synchronize fullscreen state across native fullscreen events and Escape key
if (typeof document !== "undefined") {
  document.addEventListener("fullscreenchange", () => {
    const activeFs = document.fullscreenElement;
    document.querySelectorAll(".mermaid-interactive-wrapper").forEach((w) => {
      if (w._mermaidController) {
        w._mermaidController.setFullscreenState(activeFs === w);
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll(".mermaid-interactive-wrapper.is-fullscreen").forEach((w) => {
        if (w._mermaidController) {
          w._mermaidController.setFullscreenState(false);
        }
        if (document.fullscreenElement === w && document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        }
      });
    }
  });
}

function handlePaletteToggle() {
  const nodes = document.querySelectorAll("div.mermaid");
  for (const node of nodes) {
    if (node.dataset.mermaidSource) {
      node.removeAttribute("data-processed");
      node.innerHTML = "";
      node.textContent = node.dataset.mermaidSource;
      node.dataset.mermaidPrepared = "true";
    }
  }
  renderMermaidDiagrams();
}

if (typeof MutationObserver !== "undefined" && document.body) {
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "attributes" && m.attributeName === "data-md-color-scheme") {
        handlePaletteToggle();
        break;
      }
    }
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
}

if (typeof document$ !== "undefined") {
  document$.subscribe(renderMermaidDiagrams);
} else {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderMermaidDiagrams);
  } else {
    renderMermaidDiagrams();
  }
}
