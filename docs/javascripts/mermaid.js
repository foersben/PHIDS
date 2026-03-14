function prepareMermaidBlocks() {
  const candidates = document.querySelectorAll("pre.mermaid, div.mermaid");

  for (const node of candidates) {
    if (node.dataset.mermaidPrepared === "true") {
      continue;
    }

    if (node.tagName === "PRE") {
      const code = node.querySelector("code");
      const replacement = document.createElement("div");
      replacement.className = "mermaid";
      replacement.textContent = code ? code.textContent ?? "" : node.textContent ?? "";
      replacement.dataset.mermaidPrepared = "true";
      node.replaceWith(replacement);
      continue;
    }

    node.dataset.mermaidPrepared = "true";
  }
}

function renderMermaidDiagrams() {
  if (typeof mermaid === "undefined") {
    return;
  }

  prepareMermaidBlocks();
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "neutral",
    flowchart: { htmlLabels: true },
  });

  const nodes = document.querySelectorAll("div.mermaid[data-mermaid-prepared='true']");
  if (nodes.length > 0) {
    mermaid.run({ nodes });
  }
}

if (typeof document$ !== "undefined") {
  document$.subscribe(renderMermaidDiagrams);
} else {
  document.addEventListener("DOMContentLoaded", renderMermaidDiagrams);
}
