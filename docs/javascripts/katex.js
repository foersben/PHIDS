function renderKaTeXMath() {
  if (typeof renderMathInElement === "undefined") {
    return;
  }

  renderMathInElement(document.body, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
      { left: "\\[", right: "\\]", display: true }
    ],
    throwOnError: false,
    strict: "ignore"
  });
}

if (typeof document$ !== "undefined") {
  document$.subscribe(renderKaTeXMath);
} else {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderKaTeXMath);
  } else {
    renderKaTeXMath();
  }
}
