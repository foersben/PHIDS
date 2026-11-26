# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Generate the two-panel spatial ecotone figure (fig08_ecotone_spatial_snapshot) from tick 331."""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

import matplotlib
import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

from phids.api.schemas.simulation import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.loop import SimulationLoop

matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.family"] = "sans-serif"


def _step_to_tick(cfg_path: Path, target_tick: int = 331, seed: int = 42) -> tuple[SimulationConfig, SimulationLoop]:
    cfg = SimulationConfig.model_validate(json.loads(cfg_path.read_text(encoding="utf-8")))
    random.seed(seed)
    np.random.seed(seed)
    loop = SimulationLoop(cfg, disable_replay=True)

    async def _run() -> None:
        for _ in range(target_tick):
            res = await loop.step()
            if res.terminated:
                break

    asyncio.run(_run())
    return cfg, loop


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    """Render the two-panel spatial ecotone snapshot and transition ROI at tick 331."""
    cfg_path = REPO_ROOT / "examples" / "scenarios" / "riparian_meadow_ecotone_256x256.json"
    out_dir = REPO_ROOT / "docs" / "latex" / "scientific_report" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg, loop = _step_to_tick(cfg_path, target_tick=331, seed=42)
    width, height = cfg.grid_width, cfg.grid_height

    plants_by_eid: dict[int, PlantComponent] = {}
    flora_grid = np.full((height, width), -1, dtype=np.int32)
    for ent in loop.world.query(PlantComponent):
        pl = ent.get_component(PlantComponent)
        plants_by_eid[pl.entity_id] = pl
        flora_grid[pl.y, pl.x] = pl.species_id

    swarms = [ent.get_component(SwarmComponent) for ent in loop.world.query(SwarmComponent)]
    sig_xy = np.asarray(loop.env.signal_layers[:3], dtype=np.float64).sum(axis=0)  # (W, H)
    sig_yx = sig_xy.T  # (H, W) for origin='lower'

    # ROI centred on riparian-fringe-meadow transition
    x0, y0, roi_size = 72, 196, 56
    x1, y1 = x0 + roi_size, y0 + roi_size

    palette = {
        0: "#14532d",  # p0 Populus nigra
        1: "#0d9488",  # p1 Salix purpurea
        2: "#22c55e",  # p2 Trifolium repens
        3: "#a3e635",  # p3 Lolium perenne
        4: "#eab308",  # p4 Tanacetum vulgare
        5: "#9333ea",  # p5 Brassica nigra
    }
    rgba_grid = np.zeros((height, width, 4), dtype=np.float64)
    for sid, hex_c in palette.items():
        mask = flora_grid == sid
        rgba_grid[mask] = mcolors.to_rgba(hex_c, alpha=0.92)

    # Translucent VOC plume overlay
    voc_norm = np.clip(np.log1p(sig_yx * 6.0) / np.log1p(float(sig_yx.max()) * 6.0), 0.0, 1.0)
    voc_rgba = np.zeros((height, width, 4), dtype=np.float64)
    voc_rgb = mcolors.to_rgb("#0284c7")
    voc_rgba[..., 0] = voc_rgb[0]
    voc_rgba[..., 1] = voc_rgb[1]
    voc_rgba[..., 2] = voc_rgb[2]
    voc_rgba[..., 3] = np.where(sig_yx >= 1e-4, 0.14 + 0.56 * voc_norm, 0.0)

    # Interior cardinal CMN links inside ROI
    cmn_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    seen_edges: set[tuple[int, int]] = set()
    roi_cmn_count = 0
    for eid, pl in plants_by_eid.items():
        if not (x0 <= pl.x < x1 and y0 <= pl.y < y1):
            continue
        for nb_eid in pl.mycorrhizal_connections:
            nb = plants_by_eid.get(nb_eid)
            if nb is None:
                continue
            edge = (min(eid, nb_eid), max(eid, nb_eid))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            if (x0 <= nb.x < x1 and y0 <= nb.y < y1) and (abs(pl.x - nb.x) + abs(pl.y - nb.y) == 1):
                cmn_segments.append(((float(pl.x), float(pl.y)), (float(nb.x), float(nb.y))))
                roi_cmn_count += 1

    total_edges = sum(len(pl.mycorrhizal_connections) for pl in plants_by_eid.values()) // 2
    roi_plants = sum(1 for pl in plants_by_eid.values() if x0 <= pl.x < x1 and y0 <= pl.y < y1)
    roi_swarms = [sw for sw in swarms if x0 <= sw.x < x1 and y0 <= sw.y < y1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.95), dpi=300, gridspec_kw={"wspace": 0.14})
    for ax in (ax1, ax2):
        ax.set_facecolor("#f8fafc")
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")
            spine.set_linewidth(1.0)

    # Panel (a): Full 256 x 256 Lattice
    full_extent = [-0.5, width - 0.5, -0.5, height - 0.5]
    ax1.imshow(rgba_grid, origin="lower", interpolation="nearest", extent=full_extent, zorder=2)
    ax1.imshow(voc_rgba, origin="lower", interpolation="bilinear", extent=full_extent, zorder=3)
    sx = [sw.x for sw in swarms]
    sy = [sw.y for sw in swarms]
    ss = [11.0 + 1.8 * np.sqrt(max(1, sw.population)) for sw in swarms]
    ax1.scatter(sx, sy, s=ss, c="#dc2626", edgecolors="#ffffff", linewidths=0.45, zorder=4)

    rect = mpatches.Rectangle(
        (x0 - 0.5, y0 - 0.5),
        roi_size,
        roi_size,
        fill=False,
        edgecolor="#0f172a",
        linewidth=1.6,
        linestyle="--",
        zorder=5,
    )
    ax1.add_patch(rect)
    ax1.text(
        x0 + roi_size * 0.5,
        y0 - 5.5,
        "ROI (b)",
        ha="center",
        va="top",
        fontsize=8.5,
        fontweight="bold",
        color="#0f172a",
        bbox=dict(boxstyle="round,pad=0.18", facecolor="#ffffff", edgecolor="#0f172a", alpha=0.9, lw=0.7),
        zorder=6,
    )

    # Subtle ecological band cues + wind vector
    ax1.axvline(95.5, color="#475569", linestyle=":", linewidth=0.9, alpha=0.65, zorder=2.5)
    ax1.axvline(114.5, color="#475569", linestyle=":", linewidth=0.9, alpha=0.65, zorder=2.5)
    ax1.annotate(
        "",
        xy=(52, 240),
        xytext=(12, 223.4),
        arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.55", lw=1.8, color="#0f172a"),
        zorder=6,
    )
    ax1.text(
        12,
        244,
        "Wind WSW\u2192ENE (22.5\u00b0)",
        fontsize=8.2,
        fontweight="bold",
        color="#0f172a",
        bbox=dict(boxstyle="round,pad=0.18", facecolor="#ffffff", edgecolor="#94a3b8", alpha=0.88, lw=0.6),
        zorder=6,
    )

    ax1.set_xlim(-0.5, width - 0.5)
    ax1.set_ylim(-0.5, height - 0.5)
    ax1.set_xticks([0, 64, 128, 192, 255])
    ax1.set_yticks([0, 64, 128, 192, 255])
    ax1.set_xlabel("West\u2013East Coordinate $x$ (m)", fontsize=9.5, labelpad=4)
    ax1.set_ylabel("South\u2013North Coordinate $y$ (m)", fontsize=9.5, labelpad=4)
    ax1.set_title(
        "(a) Full $256 \\times 256$ Ecotone Lattice (Tick 331)",
        fontsize=10.5,
        fontweight="bold",
        color="#0f172a",
        pad=8,
    )

    # Panel (b): Zoomed 56 x 56 Transition ROI
    roi_extent = [x0 - 0.5, x1 - 0.5, y0 - 0.5, y1 - 0.5]
    ax2.imshow(rgba_grid[y0:y1, x0:x1], origin="lower", interpolation="nearest", extent=roi_extent, zorder=2)
    ax2.imshow(voc_rgba[y0:y1, x0:x1], origin="lower", interpolation="bilinear", extent=roi_extent, zorder=3)
    if float(sig_yx[y0:y1, x0:x1].max()) > 0.05:
        gx = np.arange(x0, x1)
        gy = np.arange(y0, y1)
        ax2.contour(
            gx,
            gy,
            sig_yx[y0:y1, x0:x1],
            levels=[0.05, 0.25, 0.75],
            colors=["#0369a1"],
            linewidths=0.75,
            alpha=0.80,
            zorder=3.5,
        )

    if cmn_segments:
        lc_halo = LineCollection(cmn_segments, colors="#ffffff", linewidths=1.55, alpha=0.85, zorder=4)
        lc_edge = LineCollection(cmn_segments, colors="#9a3412", linewidths=0.80, alpha=0.92, zorder=4.1)
        ax2.add_collection(lc_halo)
        ax2.add_collection(lc_edge)

    rsx = [sw.x for sw in roi_swarms]
    rsy = [sw.y for sw in roi_swarms]
    rss = [34.0 + 3.2 * np.sqrt(max(1, sw.population)) for sw in roi_swarms]
    ax2.scatter(rsx, rsy, s=rss, c="#dc2626", edgecolors="#ffffff", linewidths=0.9, zorder=5)

    ax2.set_xlim(x0 - 0.5, x1 - 0.5)
    ax2.set_ylim(y0 - 0.5, y1 - 0.5)
    ax2.set_xticks(list(range(75, 128, 10)))
    ax2.set_yticks(list(range(200, 252, 10)))
    ax2.set_xlabel("Transition Zone Coordinate $x$ (m)", fontsize=9.5, labelpad=4)
    ax2.set_ylabel("Coordinate $y$ (m)", fontsize=9.5, labelpad=4)
    ax2.set_title(
        "(b) Zoomed $56 \\times 56$ Transition ROI ($x \\in [72, 127],\\; y \\in [196, 251]$)",
        fontsize=10.5,
        fontweight="bold",
        color="#0f172a",
        pad=8,
    )

    # Shared readable legend beneath panels
    species_labels = [
        "$p_0$ $\\mathit{Populus\\ nigra}$",
        "$p_1$ $\\mathit{Salix\\ purpurea}$",
        "$p_2$ $\\mathit{Trifolium\\ repens}$",
        "$p_3$ $\\mathit{Lolium\\ perenne}$",
        "$p_4$ $\\mathit{Tanacetum\\ vulgare}$",
        "$p_5$ $\\mathit{Brassica\\ nigra}$",
    ]
    handles = [
        *(
            mpatches.Patch(facecolor=palette[idx], edgecolor="#334155", linewidth=0.5, label=lbl)
            for idx, lbl in enumerate(species_labels)
        ),
        mlines.Line2D(
            [],
            [],
            color="#ffffff",
            marker="o",
            markerfacecolor="#dc2626",
            markeredgecolor="#0f172a",
            markersize=6.5,
            linewidth=0,
            label="Herbivore Swarms ($h_0$\u2013$h_4$)",
        ),
        mlines.Line2D([], [], color="#9a3412", linewidth=1.6, label="Cardinal CMN Links"),
        mpatches.Patch(
            facecolor="#38bdf8",
            edgecolor="#0369a1",
            alpha=0.65,
            linewidth=0.7,
            label="Airborne VOC Plumes",
        ),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=5,
        frameon=True,
        facecolor="#ffffff",
        edgecolor="#cbd5e1",
        fontsize=8.5,
        columnspacing=1.2,
        handlelength=1.6,
        bbox_to_anchor=(0.5, 0.015),
    )

    plt.subplots_adjust(left=0.055, right=0.985, top=0.92, bottom=0.20, wspace=0.14)
    pdf_path = out_dir / "fig08_ecotone_spatial_snapshot.pdf"
    png_path = out_dir / "fig08_ecotone_spatial_snapshot.png"
    plt.savefig(pdf_path)
    plt.savefig(png_path, dpi=300)
    plt.close(fig)

    print(
        f"Saved {pdf_path} | plants={len(plants_by_eid)}, swarms={len(swarms)}, "
        f"heads={sum(s.population for s in swarms)}, cmn_edges={total_edges}, "
        f"roi_plants={roi_plants}, roi_swarms={len(roi_swarms)}, roi_cmn={roi_cmn_count}"
    )


if __name__ == "__main__":
    main()
