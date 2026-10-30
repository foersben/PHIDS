/**
 * PHIDS Fullscreen Visualizer Viewport Controller
 * SPDX-FileCopyrightText: 2026 Benjamin Förster
 * SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
 *
 * Supports native HTML5 Fullscreen API with graceful fallback to CSS viewport overlay.
 */
(function () {
    /**
     * Initializes fullscreen toggle behavior for visualizer wrappers
     */
    function initFullscreenHandlers() {
        const fullscreenButtons = document.querySelectorAll(".btn-fullscreen");
        fullscreenButtons.forEach(function (btn) {
            if (btn.dataset.initialized) return;
            btn.dataset.initialized = "true";

            btn.addEventListener("click", function () {
                const targetId = btn.getAttribute("data-target");
                const wrapper = targetId ? document.getElementById(targetId) : btn.closest(".visualizer-wrapper");
                if (!wrapper) return;

                const isCurrentlyFullscreen =
                    document.fullscreenElement === wrapper ||
                    document.webkitFullscreenElement === wrapper ||
                    wrapper.classList.contains("is-fullscreen");

                if (isCurrentlyFullscreen) {
                    if (document.exitFullscreen) {
                        document.exitFullscreen().catch(function () {});
                    } else if (document.webkitExitFullscreen) {
                        document.webkitExitFullscreen();
                    }
                    wrapper.classList.remove("is-fullscreen");
                    btn.innerHTML = "⛶ Fullscreen";
                } else {
                    const requestFs =
                        wrapper.requestFullscreen ||
                        wrapper.webkitRequestFullscreen ||
                        wrapper.mozRequestFullScreen ||
                        wrapper.msRequestFullscreen;

                    if (requestFs) {
                        requestFs.call(wrapper).then(function () {
                            wrapper.classList.add("is-fullscreen");
                            btn.innerHTML = "✕ Exit Fullscreen";
                        }).catch(function () {
                            wrapper.classList.add("is-fullscreen");
                            btn.innerHTML = "✕ Exit Fullscreen";
                        });
                    } else {
                        wrapper.classList.add("is-fullscreen");
                        btn.innerHTML = "✕ Exit Fullscreen";
                    }
                }

                // Notify iframe of resized canvas
                const iframe = wrapper.querySelector("iframe");
                if (iframe && iframe.contentWindow) {
                    setTimeout(function () {
                        iframe.contentWindow.dispatchEvent(new Event("resize"));
                    }, 100);
                }
            });
        });
    }

    // Synchronize UI button state when native fullscreen changes (e.g. Esc key pressed)
    function onFullscreenChange() {
        const fullscreenWrappers = document.querySelectorAll(".visualizer-wrapper");
        const activeFsElement = document.fullscreenElement || document.webkitFullscreenElement;

        fullscreenWrappers.forEach(function (wrapper) {
            const btn = wrapper.querySelector(".btn-fullscreen");
            if (activeFsElement === wrapper) {
                wrapper.classList.add("is-fullscreen");
                if (btn) btn.innerHTML = "✕ Exit Fullscreen";
            } else if (!activeFsElement) {
                wrapper.classList.remove("is-fullscreen");
                if (btn) btn.innerHTML = "⛶ Fullscreen";
            }
        });
    }

    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);

    // Escape key fallback listener for CSS pseudo-fullscreen mode
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            const activeFullscreen = document.querySelectorAll(".visualizer-wrapper.is-fullscreen");
            activeFullscreen.forEach(function (wrapper) {
                if (document.fullscreenElement === wrapper && document.exitFullscreen) {
                    document.exitFullscreen().catch(function () {});
                }
                wrapper.classList.remove("is-fullscreen");
                const btn = wrapper.querySelector(".btn-fullscreen");
                if (btn) btn.innerHTML = "⛶ Fullscreen";
            });
        }
    });

    if (typeof document$ !== "undefined") {
        document$.subscribe(initFullscreenHandlers);
    } else {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", initFullscreenHandlers);
        } else {
            initFullscreenHandlers();
        }
    }
})();
