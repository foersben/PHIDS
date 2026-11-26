# ruff: noqa
# mypy: ignore-errors
"""Generate publication-grade figures for PHIDS scientific report.

Generates high-resolution (300 DPI) vector/raster graphics for Figure 1 and Figure 2,
with large, bold, highly legible body typography (14.5pt in Fig 1, 13.5pt in Fig 2)
optimised to completely fill cards with crisp, publication-grade aesthetics.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["DejaVu Sans", "Liberation Sans", "Helvetica", "Arial"]
matplotlib.rcParams["mathtext.fontset"] = "dejavusans"

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np


def generate_figure_1(output_dir: Path) -> None:
    """Generate Figure 1: Architectural Paradigm & Continuous-Discrete Coupling."""
    fig, ax = plt.subplots(figsize=(15.2, 8.0), dpi=300)
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 8.0)
    ax.axis("off")

    # Restrained publication typography and muted palette
    title_font = {"fontsize": 15.5, "fontweight": "bold", "color": "#0f172a"}
    card_title_font = {"fontsize": 16.0, "fontweight": "bold"}
    bullet_font = {"fontsize": 14.5, "color": "#1e293b", "linespacing": 1.42}
    badge_font = {"fontsize": 10.6, "fontweight": "bold"}

    # =========================================================================
    # LAYER 1: Lagrangian Discrete ECS Layer (Top)
    # =========================================================================
    layer1_box = patches.FancyBboxPatch(
        (0.3, 4.2), 14.6, 3.5, boxstyle="round,pad=0.2", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(layer1_box)
    ax.text(
        0.55,
        7.42,
        r"$\mathbf{Lagrangian\ Discrete\ Entity\text{-}Component\text{-}System\ (ECS)\ Layer\ \mathcal{E}_t}$ (Contiguous SoA Buffers)",
        bbox=dict(boxstyle="square,pad=0.2", facecolor="#f8fafc", edgecolor="none"),
        **title_font,
    )

    # Card 1A: Flora
    card1a = patches.FancyBboxPatch(
        (0.55, 4.5), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#2f6f5e", fc="#eef4f2", lw=1.4
    )
    ax.add_patch(card1a)
    ax.text(2.725, 6.82, "Autotrophic Flora Entities", ha="center", color="#1e4d40", **card_title_font)
    flora_text = (
        r"$\bullet$ Contiguous 1D/2D SoA buffers"
        "\n"
        r"$\bullet$ Reserve $E_i(t) \in [0, E_{\max}]$"
        "\n"
        r"$\bullet$ Armour fraction $\delta_{\mathrm{morph}} \in [0, 0.50]$"
        "\n"
        r"$\bullet$ Delay $\theta_{\mathrm{synth}} \in [8, 12]$ ticks"
    )
    ax.text(0.75, 5.62, flora_text, va="center", **bullet_font)

    # Card 1B: Defence Engine
    card1b = patches.FancyBboxPatch(
        (5.425, 4.5), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#a35c20", fc="#fdf5ed", lw=1.4
    )
    ax.add_patch(card1b)
    ax.text(7.6, 6.82, "Biotic Defence Engine", ha="center", color="#7a4112", **card_title_font)
    defense_text = (
        r"$\bullet$ Holling Type II feeding trauma"
        "\n"
        r"$\bullet$ Elicitor trigger $\to$ alert state"
        "\n"
        r"$\bullet$ Primed: $\theta_{\mathrm{primed}} \ll \theta_{\mathrm{synth}}$"
        "\n"
        r"$\bullet$ Symbiotic tax $\delta_E^{\mathrm{tax}}$ allocation"
    )
    ax.text(5.625, 5.62, defense_text, va="center", **bullet_font)

    # Card 1C: Herbivores
    card1c = patches.FancyBboxPatch(
        (10.3, 4.5), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#9a3444", fc="#f8f1f2", lw=1.4
    )
    ax.add_patch(card1c)
    ax.text(12.475, 6.82, "Heterotrophic Swarms", ha="center", color="#73222f", **card_title_font)
    herb_text = (
        r"$\bullet$ Kinematic trajectory arrays"
        "\n"
        r"$\bullet$ Headcount $N_j(t)$, reserve $E_j(t)$"
        "\n"
        r"$\bullet$ Displacement $\mathbf{d}_t$, speed $v_j$"
        "\n"
        r"$\bullet$ Charnov MVT patch departure"
    )
    ax.text(10.5, 5.62, herb_text, va="center", **bullet_font)

    # Intra-layer Arrows (Top)
    ax.annotate(
        "",
        xy=(9.78, 5.95),
        xytext=(10.3, 5.95),
        arrowprops=dict(arrowstyle="-|>", color="#9a3444", lw=1.8, mutation_scale=15),
    )
    ax.text(
        10.04,
        6.28,
        "Grazing",
        ha="center",
        va="center",
        color="#73222f",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#9a3444", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(4.9, 5.95),
        xytext=(5.425, 5.95),
        arrowprops=dict(arrowstyle="-|>", color="#2f6f5e", lw=1.8, mutation_scale=15),
    )
    ax.text(
        5.16,
        6.28,
        "Feedback",
        ha="center",
        va="center",
        color="#1e4d40",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#2f6f5e", lw=0.9),
        **badge_font,
    )

    # =========================================================================
    # LAYER 2: Eulerian Continuous Field Layer (Bottom)
    # =========================================================================
    layer2_box = patches.FancyBboxPatch(
        (0.3, 0.25), 14.6, 3.5, boxstyle="round,pad=0.2", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(layer2_box)
    ax.text(
        0.55,
        3.47,
        r"$\mathbf{Eulerian\ Continuous\ Field\ Layer\ \mathcal{G}_t}$ (Double-Buffered Toroidal Tensor $\Omega = \mathbb{T}^2$)",
        bbox=dict(boxstyle="square,pad=0.2", facecolor="#f8fafc", edgecolor="none"),
        **title_font,
    )

    # Card 2A: Atmospheric VOC
    card2a = patches.FancyBboxPatch(
        (0.55, 0.55), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#2b5b84", fc="#eff5fa", lw=1.4
    )
    ax.add_patch(card2a)
    ax.text(2.725, 2.87, "Atmospheric VOC Dispersion", ha="center", color="#1c3f5e", **card_title_font)
    voc_text = (
        r"$\bullet$ Advection by wind $\mathbf{u}_{\mathrm{wind}}$"
        "\n"
        r"$\bullet$ $5\times 5$ isotropic kernel $\mathcal{K}_{\mathrm{iso}}$"
        "\n"
        r"$\bullet$ Photolytic clearance $\lambda_s$"
        "\n"
        r"$\bullet$ Downwind conspecific plumes"
    )
    ax.text(0.75, 1.67, voc_text, va="center", **bullet_font)

    # Card 2B: Vascular & Hyphal Conduits
    card2b = patches.FancyBboxPatch(
        (5.425, 0.55), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#336666", fc="#edf5f5", lw=1.4
    )
    ax.add_patch(card2b)
    ax.text(7.6, 2.87, "Vascular & Hyphal Conduits", ha="center", color="#204545", **card_title_font)
    myco_text = (
        r"$\bullet$ Phloem withdrawal $\eta(t) \to \eta_{\min}$"
        "\n"
        r"$\bullet$ Hyphal network graph $\mathbf{A}_{uv}$"
        "\n"
        r"$\bullet$ Direct unattenuated warning"
        "\n"
        r"$\bullet$ Symbiotic link tax $\delta_E^{\mathrm{tax}}$"
    )
    ax.text(5.70, 1.67, myco_text, va="center", **bullet_font)

    # Card 2C: Chemotaxis
    card2c = patches.FancyBboxPatch(
        (10.3, 0.55), 4.35, 2.7, boxstyle="round,pad=0.15", ec="#5c4d8a", fc="#f4f2f9", lw=1.4
    )
    ax.add_patch(card2c)
    ax.text(12.475, 2.87, "Chemotactic Potential Field", ha="center", color="#3f3363", **card_title_font)
    chemo_text = (
        r"$\bullet$ Attractant vs. toxic repellent"
        "\n"
        r"$\bullet$ Jacobi potential relaxation"
        "\n"
        r"$\bullet$ Softmax heading over $\mathcal{V}$"
        "\n"
        r"$\bullet$ Dynamic sensory landscape"
    )
    ax.text(10.58, 1.67, chemo_text, va="center", **bullet_font)

    # Intra-layer Arrows (Bottom)
    ax.annotate(
        "",
        xy=(5.425, 1.85),
        xytext=(4.9, 1.85),
        arrowprops=dict(arrowstyle="<|-|>", color="#336666", lw=1.8, mutation_scale=15),
    )
    ax.text(
        5.16,
        2.18,
        "Conduits",
        ha="center",
        va="center",
        color="#204545",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#336666", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(10.3, 1.85),
        xytext=(9.78, 1.85),
        arrowprops=dict(arrowstyle="-|>", color="#5c4d8a", lw=1.8, mutation_scale=15),
    )
    ax.text(
        10.04,
        2.18,
        "Guidance",
        ha="center",
        va="center",
        color="#3f3363",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#5c4d8a", lw=0.9),
        **badge_font,
    )

    # =========================================================================
    # INTER-LAYER VERTICAL COUPLING CONDUITS (Middle Zone y = 3.25 to 4.5)
    # =========================================================================
    ax.annotate(
        "",
        xy=(1.9, 3.25),
        xytext=(1.9, 4.5),
        arrowprops=dict(arrowstyle="-|>", color="#2f6f5e", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        1.9,
        3.88,
        r"Mass Injection $Q_s$",
        ha="center",
        va="center",
        color="#1e4d40",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#2f6f5e", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(3.55, 4.5),
        xytext=(3.55, 3.25),
        arrowprops=dict(arrowstyle="-|>", color="#2b5b84", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        3.55,
        3.88,
        r"Priming $S(C_{\mathrm{voc}})$",
        ha="center",
        va="center",
        color="#1c3f5e",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#2b5b84", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(6.75, 3.25),
        xytext=(6.75, 4.5),
        arrowprops=dict(arrowstyle="-|>", color="#a35c20", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        6.75,
        3.88,
        r"Phloem Shift $\Delta\eta$",
        ha="center",
        va="center",
        color="#7a4112",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#a35c20", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(8.45, 4.5),
        xytext=(8.45, 3.25),
        arrowprops=dict(arrowstyle="-|>", color="#336666", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        8.45,
        3.88,
        "Hyphal Warning",
        ha="center",
        va="center",
        color="#204545",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#336666", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(11.6, 4.5),
        xytext=(11.6, 3.25),
        arrowprops=dict(arrowstyle="-|>", color="#5c4d8a", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        11.6,
        3.88,
        r"Olfaction $\nabla F_t$",
        ha="center",
        va="center",
        color="#3f3363",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#5c4d8a", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(13.35, 3.25),
        xytext=(13.35, 4.5),
        arrowprops=dict(arrowstyle="-|>", color="#9a3444", ls="--", lw=1.8, mutation_scale=15),
    )
    ax.text(
        13.35,
        3.88,
        r"Depletion $\Delta E$",
        ha="center",
        va="center",
        color="#73222f",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#9a3444", lw=0.9),
        **badge_font,
    )

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    png_path = output_dir / "fig01_architectural_paradigm.png"
    pdf_path = output_dir / "fig01_architectural_paradigm.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 1: {png_path} and {pdf_path}")


def generate_figure_2(output_dir: Path) -> None:
    """Generate Figure 2: Botanical Defence Hierarchy & Dual-Channel Communication Cascades."""
    fig, ax = plt.subplots(figsize=(15.2, 8.2), dpi=300)
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 8.2)
    ax.axis("off")

    panel_title_font = {"fontsize": 15.0, "fontweight": "bold", "color": "#0f172a"}
    card_title_font = {"fontsize": 14.5, "fontweight": "bold"}
    bullet_font = {"fontsize": 13.5, "color": "#1e293b", "linespacing": 1.44}
    badge_font = {"fontsize": 11.5, "fontweight": "bold"}

    # =========================================================================
    # PANEL A: Localised Attack Site (Left)
    # =========================================================================
    panela_box = patches.FancyBboxPatch(
        (0.3, 0.3), 4.5, 7.6, boxstyle="round,pad=0.2", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(panela_box)
    ax.text(
        2.55,
        7.62,
        r"$\mathbf{(a)\ Localised\ Attack\ Site\ \mathcal{E}_{\mathrm{host}}}$",
        ha="center",
        **panel_title_font,
    )

    card_a1 = patches.FancyBboxPatch(
        (0.55, 5.25), 4.0, 2.0, boxstyle="round,pad=0.15", ec="#9a3444", fc="#f8f1f2", lw=1.4
    )
    ax.add_patch(card_a1)
    ax.text(2.55, 6.95, "1. Mechanical Foliar Grazing", ha="center", color="#73222f", **card_title_font)
    a1_text = (
        r"$\bullet$ Swarm oral elicitor trigger"
        "\n"
        r"$\bullet$ Foliar trauma $\Delta E_{\mathrm{leaf}} < 0$"
        "\n"
        r"$\bullet$ Intracellular calcium wave"
    )
    ax.text(0.75, 5.95, a1_text, va="center", **bullet_font)

    card_a2 = patches.FancyBboxPatch(
        (0.55, 2.85), 4.0, 2.0, boxstyle="round,pad=0.15", ec="#a35c20", fc="#fdf5ed", lw=1.4
    )
    ax.add_patch(card_a2)
    ax.text(2.55, 4.55, "2. Synthesis Latency Window", ha="center", color="#7a4112", **card_title_font)
    a2_text = (
        r"$\bullet$ Delay $\theta_{\mathrm{synth}} \in [8, 12]$ ticks"
        "\n"
        r"$\bullet$ Vulnerability exposure gap"
        "\n"
        r"$\bullet$ Proteinase inhibitor induction"
    )
    ax.text(0.75, 3.55, a2_text, va="center", **bullet_font)

    card_a3 = patches.FancyBboxPatch(
        (0.55, 0.55), 4.0, 1.9, boxstyle="round,pad=0.15", ec="#336666", fc="#edf5f5", lw=1.4
    )
    ax.add_patch(card_a3)
    ax.text(2.55, 2.15, r"3. Phloem Translocation $\eta(t)$", ha="center", color="#204545", **card_title_font)
    a3_text = (
        r"$\bullet$ Foliar palatability withdrawal"
        "\n"
        r"$\bullet$ Attractiveness falls: $\eta \to \eta_{\min}$"
        "\n"
        r"$\bullet$ Accelerates MVT patch exit"
    )
    ax.text(0.75, 1.25, a3_text, va="center", **bullet_font)

    ax.annotate(
        "",
        xy=(2.55, 4.85),
        xytext=(2.55, 5.25),
        arrowprops=dict(arrowstyle="-|>", color="#9a3444", lw=1.8, mutation_scale=15),
    )
    ax.annotate(
        "",
        xy=(2.55, 2.45),
        xytext=(2.55, 2.85),
        arrowprops=dict(arrowstyle="-|>", color="#a35c20", lw=1.8, mutation_scale=15),
    )

    # =========================================================================
    # PANEL B: Dual Signalling Pathways (Middle)
    # =========================================================================
    panelb_box = patches.FancyBboxPatch(
        (5.35, 0.3), 4.5, 7.6, boxstyle="round,pad=0.2", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(panelb_box)
    ax.text(7.6, 7.62, r"$\mathbf{(b)\ Dual\ Signalling\ Pathways}$", ha="center", **panel_title_font)

    card_b1 = patches.FancyBboxPatch(
        (5.6, 4.15), 4.0, 3.1, boxstyle="round,pad=0.15", ec="#2b5b84", fc="#eff5fa", lw=1.4
    )
    ax.add_patch(card_b1)
    ax.text(7.6, 6.95, "Airborne Channel (Atmosphere)", ha="center", color="#1c3f5e", **card_title_font)
    b1_text = (
        r"$\bullet$ GLV volatiles and terpenoids"
        "\n"
        r"$\bullet$ Advection-diffusion PDE:"
        "\n"
        r"   $\partial_t C_s + \mathbf{u}\cdot\nabla C_s = D_s\nabla^2 C_s - \lambda_s C_s$"
        "\n"
        r"$\bullet$ Fast reach, wind-dependent"
        "\n"
        r"$\bullet$ Spatial dilution & eavesdropping"
    )
    ax.text(5.78, 5.35, b1_text, va="center", **bullet_font)

    card_b2 = patches.FancyBboxPatch(
        (5.6, 0.55), 4.0, 3.1, boxstyle="round,pad=0.15", ec="#6b4f3b", fc="#f5f1ee", lw=1.4
    )
    ax.add_patch(card_b2)
    ax.text(7.6, 3.35, "Subterranean Hyphal Conduit", ha="center", color="#4a3425", **card_title_font)
    b2_text = (
        r"$\bullet$ Hyphal network graph $\mathbf{A}_{uv}$"
        "\n"
        r"$\bullet$ Direct relay gain $g_{\mathrm{relay}} \geq 1$"
        "\n"
        r"$\bullet$ Unattenuated upwind warning"
        "\n"
        r"$\bullet$ Wind-vector invariant routing"
        "\n"
        r"$\bullet$ Symbiotic link tax $\delta_E^{\mathrm{tax}}$"
    )
    ax.text(5.78, 1.80, b2_text, va="center", **bullet_font)

    # =========================================================================
    # PANEL C: Neighbour Priming (Right)
    # =========================================================================
    panelc_box = patches.FancyBboxPatch(
        (10.4, 0.3), 4.5, 7.6, boxstyle="round,pad=0.2", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(panelc_box)
    ax.text(
        12.65,
        7.62,
        r"$\mathbf{(c)\ Neighbour\ Priming\ \mathcal{E}_{\mathrm{primed}}}$",
        ha="center",
        **panel_title_font,
    )

    card_c1 = patches.FancyBboxPatch(
        (10.65, 5.25), 4.0, 2.0, boxstyle="round,pad=0.15", ec="#2f6f7e", fc="#eef5f7", lw=1.4
    )
    ax.add_patch(card_c1)
    ax.text(12.65, 6.95, "1. Hill Receptor Perception", ha="center", color="#1e4b56", **card_title_font)
    c1_text = (
        r"$\bullet$ Sigmoidal: $S(C) = C^n / (K_d^n + C^n)$"
        "\n"
        r"$\bullet$ Inactive MAPK pool buildup"
        "\n"
        r"$\bullet$ Baseline upkeep tax ($\approx 1\%$)"
    )
    ax.text(10.85, 5.95, c1_text, va="center", **bullet_font)

    card_c2 = patches.FancyBboxPatch(
        (10.65, 2.85), 4.0, 2.0, boxstyle="round,pad=0.15", ec="#2f6f5e", fc="#eef4f2", lw=1.4
    )
    ax.add_patch(card_c2)
    ax.text(12.65, 4.55, "2. Latency Compression", ha="center", color="#1e4d40", **card_title_font)
    c2_text = (
        r"$\bullet$ Primed: $\theta_{\mathrm{primed}} \ll \theta_{\mathrm{synth}}$"
        "\n"
        r"$\bullet$ Pre-conditioned enzyme state"
        "\n"
        r"$\bullet$ Rapid toxin onset upon attack"
    )
    ax.text(10.85, 3.55, c2_text, va="center", **bullet_font)

    card_c3 = patches.FancyBboxPatch(
        (10.65, 0.55), 4.0, 1.9, boxstyle="round,pad=0.15", ec="#5c4d8a", fc="#f4f2f9", lw=1.4
    )
    ax.add_patch(card_c3)
    ax.text(12.65, 2.15, "3. Repellent Barrier Deployed", ha="center", color="#3f3363", **card_title_font)
    c3_text = (
        r"$\bullet$ Secondary allelochemical surge"
        "\n"
        r"$\bullet$ Inverts chemotactic potential $F_t$"
        "\n"
        r"$\bullet$ Swarm cluster deflected/starved"
    )
    ax.text(10.85, 1.25, c3_text, va="center", **bullet_font)

    ax.annotate(
        "",
        xy=(12.65, 4.85),
        xytext=(12.65, 5.25),
        arrowprops=dict(arrowstyle="-|>", color="#2f6f7e", lw=1.8, mutation_scale=15),
    )
    ax.annotate(
        "",
        xy=(12.65, 2.45),
        xytext=(12.65, 2.85),
        arrowprops=dict(arrowstyle="-|>", color="#2f6f5e", lw=1.8, mutation_scale=15),
    )

    # Inter-panel arrows
    ax.annotate(
        "",
        xy=(5.6, 5.65),
        xytext=(4.55, 5.65),
        arrowprops=dict(arrowstyle="-|>", color="#2b5b84", lw=2.0, mutation_scale=15),
    )
    ax.text(
        5.075,
        6.0,
        "VOC Plumes",
        ha="center",
        va="center",
        color="#1c3f5e",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#2b5b84", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(10.65, 5.65),
        xytext=(9.6, 5.65),
        arrowprops=dict(arrowstyle="-|>", color="#2b5b84", lw=2.0, mutation_scale=15),
    )
    ax.text(
        10.125,
        6.0,
        "Plume Inflow",
        ha="center",
        va="center",
        color="#1c3f5e",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#2b5b84", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(5.6, 2.30),
        xytext=(4.55, 2.30),
        arrowprops=dict(arrowstyle="-|>", color="#6b4f3b", lw=2.0, mutation_scale=15),
    )
    ax.text(
        5.075,
        2.65,
        "Hyphal Pulse",
        ha="center",
        va="center",
        color="#4a3425",
        bbox=dict(boxstyle="round,pad=0.20", facecolor="white", edgecolor="#6b4f3b", lw=0.9),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(10.65, 2.30),
        xytext=(9.6, 2.30),
        arrowprops=dict(arrowstyle="-|>", color="#6b4f3b", lw=2.0, mutation_scale=15),
    )
    ax.text(
        10.125,
        2.65,
        "Hyphal Relay",
        ha="center",
        va="center",
        color="#4a3425",
        bbox=dict(boxstyle="round,pad=0.20", facecolor="white", edgecolor="#6b4f3b", lw=0.9),
        **badge_font,
    )

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    png_path = output_dir / "fig02_botanical_defense_hierarchy.png"
    pdf_path = output_dir / "fig02_botanical_defense_hierarchy.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 2: {png_path} and {pdf_path}")


def generate_figure_3(output_dir: Path) -> None:
    """Generate Figure 3: Dual-Domain Isomorphism and Distributed Alert Topologies."""
    fig, ax = plt.subplots(figsize=(15.2, 8.5), dpi=300)
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    panel_title_font = {"fontsize": 14.5, "fontweight": "bold", "color": "#0f172a"}
    card_title_font = {"fontsize": 14.2, "fontweight": "bold"}
    bullet_font = {"fontsize": 13.0, "color": "#1e293b", "linespacing": 1.42}
    badge_font = {"fontsize": 11.0, "fontweight": "bold"}

    # =========================================================================
    # PANEL A: Botanical Ecological Domain (Left)
    # =========================================================================
    panela_box = patches.FancyBboxPatch(
        (0.35, 0.25), 6.8, 8.0, boxstyle="round,pad=0.2", ec="#2f6f5e", fc="#f4f8f6", ls="--", lw=1.3
    )
    ax.add_patch(panela_box)
    ax.text(3.75, 7.92, r"$\mathbf{(a)\ Botanical\ Ecological\ Domain}$", ha="center", **panel_title_font)

    card_a1 = patches.FancyBboxPatch(
        (0.65, 5.38), 6.2, 2.15, boxstyle="round,pad=0.10", ec="#2f6f5e", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_a1)
    ax.text(3.75, 7.22, "1. Autotrophic Host vs. Herbivorous Forager", ha="center", color="#1e4d40", **card_title_font)
    a1_text = (
        r"$\bullet$ Finite photosynthate reserve: $E_i(t) \in [0, E_{\max}]$"
        "\n"
        r"$\bullet$ Foliar tissue grazing: trauma $\Delta E_{\mathrm{leaf}} < 0$"
        "\n"
        r"$\bullet$ Herbivore swarm: Holling Type II intake"
        "\n"
        r"$\bullet$ Chemotaxis along gradient $\nabla F_t$"
    )
    ax.text(0.85, 6.22, a1_text, va="center", **bullet_font)

    card_a2 = patches.FancyBboxPatch(
        (0.65, 2.90), 6.2, 2.15, boxstyle="round,pad=0.10", ec="#336666", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_a2)
    ax.text(3.75, 4.74, "2. Dual Semiochemical Alert Conduits", ha="center", color="#204545", **card_title_font)
    a2_text = (
        r"$\bullet$ Airborne VOCs: advection-diffusion-reaction PDE"
        "\n"
        r"$\bullet$ Local reach subject to wind drift & dilution"
        "\n"
        r"$\bullet$ Subterranean mycorrhizal graph $\mathbf{A}_{uv}$"
        "\n"
        r"$\bullet$ Direct unattenuated warning (tax $\delta_E^{\mathrm{tax}}$)"
    )
    ax.text(0.85, 3.74, a2_text, va="center", **bullet_font)

    card_a3 = patches.FancyBboxPatch(
        (0.65, 0.45), 6.2, 2.12, boxstyle="round,pad=0.10", ec="#a35c20", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_a3)
    ax.text(3.75, 2.24, "3. Botanical Priming & Phloem Shift", ha="center", color="#7a4112", **card_title_font)
    a3_text = (
        r"$\bullet$ Downwind neighbour Hill priming $S(C_{\mathrm{voc}})$"
        "\n"
        r"$\bullet$ Synthesis delay compressed: $\theta_{\mathrm{primed}} \ll \theta_{\mathrm{synth}}$"
        "\n"
        r"$\bullet$ Phloem shift: apparent foliar nutrition $\eta(t)$"
        "\n"
        r"$\bullet$ Reduced palatability accelerates patch exit"
    )
    ax.text(0.85, 1.27, a3_text, va="center", **bullet_font)

    # =========================================================================
    # PANEL B: Distributed WSN Cybersecurity Domain (Right)
    # =========================================================================
    panelb_box = patches.FancyBboxPatch(
        (8.05, 0.25), 6.8, 8.0, boxstyle="round,pad=0.2", ec="#2b5b84", fc="#f3f6fa", ls="--", lw=1.3
    )
    ax.add_patch(panelb_box)
    ax.text(11.45, 7.92, r"$\mathbf{(b)\ Distributed\ WSN\ Cybersecurity\ Domain}$", ha="center", **panel_title_font)

    card_b1 = patches.FancyBboxPatch(
        (8.35, 5.38), 6.2, 2.15, boxstyle="round,pad=0.10", ec="#2b5b84", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_b1)
    ax.text(11.45, 7.22, "1. Static Sensor Node vs. Mobile Intrusion", ha="center", color="#1c3f5e", **card_title_font)
    b1_text = (
        r"$\bullet$ Finite battery energy budget: $B_i(t) \in [0, B_{\max}]$"
        "\n"
        r"$\bullet$ Denial-of-Sleep attack: battery drain $\Delta B_i < 0$"
        "\n"
        r"$\bullet$ Mobile botnet: packet flooding & jamming"
        "\n"
        r"$\bullet$ Threat probes targeting open port gradients"
    )
    ax.text(8.55, 6.22, b1_text, va="center", **bullet_font)

    card_b2 = patches.FancyBboxPatch(
        (8.35, 2.90), 6.2, 2.15, boxstyle="round,pad=0.10", ec="#2f6f7e", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_b2)
    ax.text(11.45, 4.74, "2. Dual Wireless Alert Topologies", ha="center", color="#1e4b56", **card_title_font)
    b2_text = (
        r"$\bullet$ Unencrypted RF broadcast frames (1-2-hop MAC)"
        "\n"
        r"$\bullet$ Fast dissemination with path loss & sniffing"
        "\n"
        r"$\bullet$ Authenticated out-of-band mesh links $\mathbf{K}_{uv}$"
        "\n"
        r"$\bullet$ Cryptographically verified relay (routing tax)"
    )
    ax.text(8.55, 3.74, b2_text, va="center", **bullet_font)

    card_b3 = patches.FancyBboxPatch(
        (8.35, 0.45), 6.2, 2.12, boxstyle="round,pad=0.10", ec="#8c3b5c", fc="#ffffff", lw=1.4
    )
    ax.add_patch(card_b3)
    ax.text(11.45, 2.24, "3. Pre-Allocated Security & QoS Throttling", ha="center", color="#682741", **card_title_font)
    b3_text = (
        r"$\bullet$ Neighbour pre-stages verification & filter rules"
        "\n"
        r"$\bullet$ Response latency compressed: $\tau_{\mathrm{primed}} \ll \tau_{\mathrm{cold}}$"
        "\n"
        r"$\bullet$ Dynamic QoS throttling: non-essential ports masked"
        "\n"
        r"$\bullet$ Adversary payoff drops, inducing MVT exit"
    )
    ax.text(8.55, 1.25, b3_text, va="center", **bullet_font)

    # =========================================================================
    # CENTRAL ISOMORPHISM CONNECTORS (Middle Column x = 6.85 to 8.35)
    # =========================================================================
    ax.annotate(
        "",
        xy=(8.35, 6.45),
        xytext=(6.85, 6.45),
        arrowprops=dict(arrowstyle="<|-|>", color="#2b5b84", lw=2.0, mutation_scale=15),
    )
    ax.text(
        7.60,
        6.45,
        "Entity\nMapping",
        ha="center",
        va="center",
        color="#1c3f5e",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#ffffff", edgecolor="#2b5b84", lw=1.1),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(8.35, 3.95),
        xytext=(6.85, 3.95),
        arrowprops=dict(arrowstyle="<|-|>", color="#336666", lw=2.0, mutation_scale=15),
    )
    ax.text(
        7.60,
        3.95,
        "Channel\nMapping",
        ha="center",
        va="center",
        color="#204545",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#ffffff", edgecolor="#336666", lw=1.1),
        **badge_font,
    )

    ax.annotate(
        "",
        xy=(8.35, 1.52),
        xytext=(6.85, 1.52),
        arrowprops=dict(arrowstyle="<|-|>", color="#8c3b5c", lw=2.0, mutation_scale=15),
    )
    ax.text(
        7.60,
        1.52,
        "Protocol\nMapping",
        ha="center",
        va="center",
        color="#682741",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#ffffff", edgecolor="#8c3b5c", lw=1.1),
        **badge_font,
    )

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    png_path = output_dir / "fig03_wsn_isomorphism.png"
    pdf_path = output_dir / "fig03_wsn_isomorphism.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 3: {png_path} and {pdf_path}")


def generate_figure_4(output_dir: Path) -> None:
    """Generate Figure 4: Methodological Landscape & Architectural Taxonomy."""
    fig, ax = plt.subplots(figsize=(15.2, 8.5), dpi=300)
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    main_title_font = {"fontsize": 15.0, "fontweight": "bold", "color": "#0f172a"}
    col_header_font = {"fontsize": 13.0, "fontweight": "bold"}
    row_label_font = {"fontsize": 11.2, "fontweight": "bold", "color": "#334155"}
    card_title_font = {"fontsize": 13.0, "fontweight": "bold"}
    phids_title_font = {"fontsize": 13.8, "fontweight": "bold", "color": "#1e4d40"}
    bullet_font = {"fontsize": 10.6, "color": "#1e293b", "linespacing": 1.38}
    phids_bullet_font = {"fontsize": 10.8, "color": "#0f2e26", "linespacing": 1.38}

    # Outer border
    outer_box = patches.FancyBboxPatch(
        (0.35, 0.25), 14.5, 8.0, boxstyle="round,pad=0.2", ec="#94a3b8", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(outer_box)
    ax.text(
        7.60,
        7.95,
        r"$\mathbf{Methodological\ Landscape\ and\ Simulation\ Architectural\ Taxonomy}$",
        ha="center",
        **main_title_font,
    )

    # Column Headers (Spatial Scale Classification)
    ax.text(
        2.75,
        7.48,
        r"$\mathbf{Macro\text{-}Scale\ Landscapes\ (>100\ m)}$",
        ha="center",
        color="#73222f",
        **col_header_font,
    )
    ax.text(
        7.60,
        7.48,
        r"$\mathbf{Meso\text{-}Scale\ Biotopes\ (1\text{-}100\ m)}$",
        ha="center",
        color="#1e4d40",
        **col_header_font,
    )
    ax.text(
        12.45,
        7.48,
        r"$\mathbf{Micro\text{-}Scale\ Tissues\ (<1\ mm)}$",
        ha="center",
        color="#1e4b56",
        **col_header_font,
    )

    ax.plot([0.6, 14.6], [4.15, 4.15], color="#cbd5e1", lw=1.2, ls=":")

    # COLUMN 1: Macro-Scale
    card_landis = patches.FancyBboxPatch(
        (0.60, 4.35), 4.30, 2.85, boxstyle="round,pad=0.15", ec="#9a3444", fc="#f8f1f2", lw=1.4
    )
    ax.add_patch(card_landis)
    ax.text(2.75, 6.88, "LANDIS-II / ALMaSS", ha="center", color="#73222f", **card_title_font)
    ax.text(
        2.75, 6.60, "(Landscape Forest & Animal ABM)", ha="center", fontsize=10.2, fontstyle="italic", color="#5d4037"
    )
    c_landis_text = (
        r"$\bullet$ Domain: Forest succession & wildlife spread"
        "\n"
        r"$\bullet$ Model: Spatial automata / OOP agents"
        "\n"
        r"$\bullet$ Stride: Hourly to seasonal habitat steps"
        "\n"
        r"$\bullet$ Limits: No reactive semiochemical PDEs"
        "\n"
        r"$\bullet$ Focus: Landscape biodiversity dynamics"
    )
    ax.text(0.78, 5.42, c_landis_text, va="center", **bullet_font)

    card_simplace = patches.FancyBboxPatch(
        (0.60, 1.05), 4.30, 2.85, boxstyle="round,pad=0.15", ec="#64748b", fc="#f1f5f9", lw=1.4
    )
    ax.add_patch(card_simplace)
    ax.text(2.75, 3.58, "SIMPLACE / MONICA", ha="center", color="#1e293b", **card_title_font)
    ax.text(
        2.75,
        3.30,
        "(Continuous Macro Biogeochemistry)",
        ha="center",
        fontsize=10.2,
        fontstyle="italic",
        color="#475569",
    )
    c_simplace_text = (
        r"$\bullet$ Domain: Crop phenology & soil carbon"
        "\n"
        r"$\bullet$ Model: 1D vertical columns, Richards ODEs"
        "\n"
        r"$\bullet$ Stride: Daily agronomic steps ($\Delta t = 24\,\text{h}$)"
        "\n"
        r"$\bullet$ Limits: No 2D reactive fields or swarms"
        "\n"
        r"$\bullet$ Focus: Regional agricultural yield forecasts"
    )
    ax.text(0.78, 2.12, c_simplace_text, va="center", **bullet_font)

    # COLUMN 2: Meso-Scale (PHIDS + NetLogo/Mesa)
    card_phids = patches.FancyBboxPatch(
        (5.30, 4.30), 4.60, 2.95, boxstyle="round,pad=0.12", ec="#2f6f5e", fc="#eef4f2", lw=2.2
    )
    ax.add_patch(card_phids)
    ax.text(7.60, 6.95, "PHIDS (This Work)", ha="center", **phids_title_font)
    ax.text(
        7.60,
        6.67,
        r"$\mathbf{Coupled\ Hybrid\ Meso\text{-}Scale\ Framework}$",
        ha="center",
        fontsize=10.5,
        color="#2f6f5e",
    )
    c_phids_text = (
        r"$\bullet$ Domain: Plant-herbivore chemical defence"
        "\n"
        r"$\bullet$ Model: SoA ECS + Eulerian 2D PDEs"
        "\n"
        r"$\bullet$ Strides: Multi-rate ($\Delta t = 1, 24, 168\,\text{h}$)"
        "\n"
        r"$\bullet$ Conduits: Airborne VOCs + hyphal graph"
        "\n"
        r"$\bullet$ Latency: $1.25\text{-}2.59\,\text{ms}$/tick ($>60\,\text{Hz}$)"
    )
    ax.text(5.48, 5.44, c_phids_text, va="center", **phids_bullet_font)

    card_netlogo = patches.FancyBboxPatch(
        (5.30, 1.05), 4.60, 2.85, boxstyle="round,pad=0.15", ec="#5c4d8a", fc="#f4f2f9", lw=1.4
    )
    ax.add_patch(card_netlogo)
    ax.text(7.60, 3.58, "NetLogo / Mesa", ha="center", color="#3f3363", **card_title_font)
    ax.text(
        7.60, 3.30, "(General-Purpose ABM Toolkits)", ha="center", fontsize=10.2, fontstyle="italic", color="#5c4d8a"
    )
    c_netlogo_text = (
        r"$\bullet$ Domain: General-purpose ABM toolkits"
        "\n"
        r"$\bullet$ Model: Interpreted OOP agent objects"
        "\n"
        r"$\bullet$ Stride: User ticks; single-threaded runtime"
        "\n"
        r"$\bullet$ Limits: No built-in PDE solvers; $\mathcal{O}(N^2)$ cost"
        "\n"
        r"$\bullet$ Focus: Rapid prototyping & education"
    )
    ax.text(5.48, 2.12, c_netlogo_text, va="center", **bullet_font)

    # COLUMN 3: Micro-Scale
    card_cc3d = patches.FancyBboxPatch(
        (10.30, 4.35), 4.30, 2.85, boxstyle="round,pad=0.15", ec="#2f6f7e", fc="#eef5f7", lw=1.4
    )
    ax.add_patch(card_cc3d)
    ax.text(12.45, 6.88, "CompuCell3D (CC3D)", ha="center", color="#1e4b56", **card_title_font)
    ax.text(
        12.45,
        6.60,
        "(Micro-Scale Tissue Morphogenesis)",
        ha="center",
        fontsize=10.2,
        fontstyle="italic",
        color="#2f6f7e",
    )
    c_cc3d_text = (
        r"$\bullet$ Domain: Morphogenesis & tumour growth"
        "\n"
        r"$\bullet$ Model: Cellular Potts Model (CPM) + PDEs"
        "\n"
        r"$\bullet$ Stride: Sub-cellular Monte Carlo spin flips"
        "\n"
        r"$\bullet$ Limits: Sub-cellular overhead at macro scales"
        "\n"
        r"$\bullet$ Focus: Embryogenesis & cellular adhesion"
    )
    ax.text(10.48, 5.42, c_cc3d_text, va="center", **bullet_font)

    card_vcell = patches.FancyBboxPatch(
        (10.30, 1.05), 4.30, 2.85, boxstyle="round,pad=0.15", ec="#64748b", fc="#f1f5f9", lw=1.4
    )
    ax.add_patch(card_vcell)
    ax.text(12.45, 3.58, "HAL / MCell4", ha="center", color="#1e293b", **card_title_font)
    ax.text(
        12.45,
        3.30,
        "(Cellular & Subcellular Reaction-Diffusion)",
        ha="center",
        fontsize=10.2,
        fontstyle="italic",
        color="#475569",
    )
    c_vcell_text = (
        r"$\bullet$ Domain: Tumour & synaptic signalling"
        "\n"
        r"$\bullet$ Model: Automata / Brownian particle PDEs"
        "\n"
        r"$\bullet$ Stride: Sub-cellular steps & continuous fluxes"
        "\n"
        r"$\bullet$ Limits: No macro foraging or CMN conduits"
        "\n"
        r"$\bullet$ Focus: Tissue & intracellular kinetics"
    )
    ax.text(10.48, 2.12, c_vcell_text, va="center", **bullet_font)

    ax.text(
        7.60,
        0.55,
        r"$\mathbf{Coupling\ Paradigms:}$ Top Row: Spatially Explicit Kinematics & Hybrid PDEs $\quad\vert\quad$ Bottom Row: 1D Columns, Stiff ODEs & General Toolkits",
        ha="center",
        va="center",
        **row_label_font,
    )

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    png_path = output_dir / "fig04_methodological_landscape.png"
    pdf_path = output_dir / "fig04_methodological_landscape.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 4: {png_path} and {pdf_path}")


def generate_figure_5(output_dir: Path) -> None:
    """Generate Figure 5: Operator Splitting Pipeline and Multi-Scale Loop Decoupling."""
    fig, ax = plt.subplots(figsize=(15.2, 8.4), dpi=300)
    ax.set_xlim(0, 15.2)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    panel_title_font = {"fontsize": 14.0, "fontweight": "bold", "color": "#0f172a"}
    stage_title_font = {"fontsize": 12.6, "fontweight": "bold"}
    stage_formula_font = {"fontsize": 12.2, "fontweight": "bold"}
    stage_detail_font = {"fontsize": 10.6, "color": "#334155"}
    card_title_font = {"fontsize": 13.0, "fontweight": "bold"}
    bullet_font = {"fontsize": 11.6, "color": "#1e293b", "linespacing": 1.38}
    arrow_label_font = {"fontsize": 10.6, "fontweight": "bold"}

    # =========================================================================
    # PANEL (a): Reaction-Diffusion Operator-Splitting Pipeline (Left)
    # =========================================================================
    panel_a_box = patches.FancyBboxPatch(
        (0.35, 0.30), 6.95, 7.80, boxstyle="round,pad=0.15", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(panel_a_box)
    ax.text(
        3.825,
        7.85,
        r"$\mathbf{(a)\ Operator\text{-}Splitting\ Transport\ Pipeline}$",
        ha="center",
        bbox=dict(boxstyle="square,pad=0.15", facecolor="#f8fafc", edgecolor="none"),
        **panel_title_font,
    )

    buf_read = patches.FancyBboxPatch(
        (0.60, 7.00), 6.45, 0.50, boxstyle="round,pad=0.12", ec="#2b5b84", fc="#eff5fa", lw=1.4
    )
    ax.add_patch(buf_read)
    ax.text(
        3.825,
        7.25,
        r"$\mathbf{Read\ Buffer\ (Ingress):}\ C^t(\mathbf{x}) \in \mathbb{R}^{W \times H}$",
        ha="center",
        va="center",
        color="#1c3f5e",
        fontsize=12.4,
        fontweight="bold",
    )

    ax.annotate(
        "",
        xy=(3.825, 6.77),
        xytext=(3.825, 6.98),
        arrowprops=dict(arrowstyle="-|>", color="#2b5b84", lw=1.8, mutation_scale=14),
    )

    stg1 = patches.FancyBboxPatch(
        (0.60, 5.85), 6.45, 0.90, boxstyle="round,pad=0.12", ec="#9a3444", fc="#f8f1f2", lw=1.4
    )
    ax.add_patch(stg1)
    ax.text(3.825, 6.52, "Stage 1: Localised Point Mass Injection", ha="center", color="#73222f", **stage_title_font)
    ax.text(
        3.825,
        6.27,
        r"$C^{*}_{\mathrm{source}}(\mathbf{x}) = C^t(\mathbf{x}) + Q_s^t(\mathbf{x})\Delta t / h^2$",
        ha="center",
        color="#9a3444",
        **stage_formula_font,
    )
    ax.text(3.825, 5.99, "Active volatile synthesis flux injected prior to transport", ha="center", **stage_detail_font)

    ax.annotate(
        "",
        xy=(3.825, 5.62),
        xytext=(3.825, 5.83),
        arrowprops=dict(arrowstyle="-|>", color="#9a3444", lw=1.8, mutation_scale=14),
    )

    stg2 = patches.FancyBboxPatch(
        (0.60, 4.70), 6.45, 0.90, boxstyle="round,pad=0.12", ec="#2b5b84", fc="#eff5fa", lw=1.4
    )
    ax.add_patch(stg2)
    ax.text(3.825, 5.37, "Stage 2: Semi-Lagrangian Wind Advection", ha="center", color="#1c3f5e", **stage_title_font)
    ax.text(
        3.825,
        5.12,
        r"$\tilde{C}^t(\mathbf{x}) = C^{*}_{\mathrm{source}}(\mathbf{x} - \mathbf{u}_{\mathrm{wind}}\Delta t)$",
        ha="center",
        color="#2b5b84",
        **stage_formula_font,
    )
    ax.text(
        3.825,
        4.84,
        "Unconditionally stable back-trace; bilinear upwind interpolation",
        ha="center",
        **stage_detail_font,
    )

    ax.annotate(
        "",
        xy=(3.825, 4.47),
        xytext=(3.825, 4.68),
        arrowprops=dict(arrowstyle="-|>", color="#2b5b84", lw=1.8, mutation_scale=14),
    )

    stg3 = patches.FancyBboxPatch(
        (0.60, 3.55), 6.45, 0.90, boxstyle="round,pad=0.12", ec="#336666", fc="#edf5f5", lw=1.4
    )
    ax.add_patch(stg3)
    ax.text(3.825, 4.22, "Stage 3: Isotropic Gaussian Diffusion", ha="center", color="#204545", **stage_title_font)
    ax.text(
        3.825,
        3.97,
        r"$C^{*}_{\mathrm{diff}}(\mathbf{x}) = (\mathcal{K}_{\mathrm{iso}} * \tilde{C}^t)(\mathbf{x}) \quad (5 \times 5\ \mathrm{Stencil},\ \sigma = 0.4)$",
        ha="center",
        color="#336666",
        **stage_formula_font,
    )
    ax.text(
        3.825, 3.69, "Symmetric spatial convolution; prevents half-cell phase drift", ha="center", **stage_detail_font
    )

    ax.annotate(
        "",
        xy=(3.825, 3.32),
        xytext=(3.825, 3.53),
        arrowprops=dict(arrowstyle="-|>", color="#336666", lw=1.8, mutation_scale=14),
    )

    stg4 = patches.FancyBboxPatch(
        (0.60, 2.40), 6.45, 0.90, boxstyle="round,pad=0.12", ec="#a35c20", fc="#fdf5ed", lw=1.4
    )
    ax.add_patch(stg4)
    ax.text(
        3.825, 3.07, "Stage 4: Photolytic Clearance & Dissipation", ha="center", color="#7a4112", **stage_title_font
    )
    ax.text(
        3.825,
        2.82,
        r"$C^{*}_{\mathrm{decay}}(\mathbf{x}) = \gamma_s \cdot C^{*}_{\mathrm{diff}}(\mathbf{x}) \quad (\gamma_s = \exp(-\lambda_s \Delta t))$",
        ha="center",
        color="#a35c20",
        **stage_formula_font,
    )
    ax.text(3.825, 2.54, "Photolytic clearance retention factor across field slices", ha="center", **stage_detail_font)

    ax.annotate(
        "",
        xy=(3.825, 2.17),
        xytext=(3.825, 2.38),
        arrowprops=dict(arrowstyle="-|>", color="#a35c20", lw=1.8, mutation_scale=14),
    )

    stg5 = patches.FancyBboxPatch(
        (0.60, 1.25), 6.45, 0.90, boxstyle="round,pad=0.12", ec="#5c4d8a", fc="#f4f2f9", lw=1.4
    )
    ax.add_patch(stg5)
    ax.text(
        3.825, 1.92, "Stage 5: Macroscopic Sparsity Cutoff (Zeroing)", ha="center", color="#3f3363", **stage_title_font
    )
    ax.text(
        3.825,
        1.67,
        r"$C^{t+1}(\mathbf{x}) = \mathbf{1}_{\{C^{*}_{\mathrm{decay}} \geq 10^{-4}\}} \odot C^{*}_{\mathrm{decay}}(\mathbf{x})$",
        ha="center",
        color="#5c4d8a",
        **stage_formula_font,
    )
    ax.text(
        3.825, 1.39, "Clamps trace tails below 1e-4 to zero; keeps active sets sparse", ha="center", **stage_detail_font
    )

    ax.annotate(
        "",
        xy=(3.825, 1.02),
        xytext=(3.825, 1.23),
        arrowprops=dict(arrowstyle="-|>", color="#5c4d8a", lw=1.8, mutation_scale=14),
    )

    buf_write = patches.FancyBboxPatch(
        (0.60, 0.50), 6.45, 0.50, boxstyle="round,pad=0.12", ec="#2f6f5e", fc="#eef4f2", lw=1.4
    )
    ax.add_patch(buf_write)
    ax.text(
        3.825,
        0.75,
        r"$\mathbf{Write\ Buffer\ (Egress):}\ C^{t+1}(\mathbf{x}) \in \mathbb{R}^{W \times H}$",
        ha="center",
        va="center",
        color="#1e4d40",
        fontsize=12.4,
        fontweight="bold",
    )

    # =========================================================================
    # PANEL (b): Multi-Scale Temporal Decoupling Architecture (Right)
    # =========================================================================
    panel_b_box = patches.FancyBboxPatch(
        (7.90, 0.30), 6.95, 7.80, boxstyle="round,pad=0.15", ec="#64748b", fc="#f8fafc", ls="--", lw=1.2
    )
    ax.add_patch(panel_b_box)
    ax.text(
        11.375,
        7.85,
        r"$\mathbf{(b)\ Multi\text{-}Scale\ Temporal\ Decoupling}$",
        ha="center",
        bbox=dict(boxstyle="square,pad=0.15", facecolor="#f8fafc", edgecolor="none"),
        **panel_title_font,
    )

    card_b1 = patches.FancyBboxPatch(
        (8.15, 5.45), 6.45, 2.05, boxstyle="round,pad=0.15", ec="#2b5b84", fc="#eff5fa", lw=1.5
    )
    ax.add_patch(card_b1)
    ax.text(
        11.375,
        7.22,
        r"$\mathbf{Fast\ Loop:\ Hourly\ Stride\ (\Delta t = 1\,\mathrm{h},\ >60\,\mathrm{Hz})}$",
        ha="center",
        color="#1c3f5e",
        **card_title_font,
    )
    b1_text = (
        r"$\bullet$ Semi-Lagrangian advection & $5\times 5$ Gaussian diffusion"
        "\n"
        r"$\bullet$ Jacobi relaxation for chemotactic potential $F_t(x, y)$"
        "\n"
        r"$\bullet$ Swarm stochastic taxis via Boltzmann softmax"
        "\n"
        r"$\bullet$ Hill kinetic priming triggers ($S(C) \geq \tau_{\mathrm{prim}}$)"
        "\n"
        r"$\bullet$ $\mathcal{O}(W \cdot H)$ double-buffered compiled array updates"
    )
    ax.text(8.33, 6.22, b1_text, va="center", **bullet_font)

    ax.plot([11.375, 11.375], [5.43, 5.28], color="#a35c20", lw=1.8)
    ax.text(
        11.375,
        5.12,
        r"$\mathbf{24\times\ Hourly\ Ticks}\ (\mathrm{Diurnal\ Synchronisation})$",
        ha="center",
        va="center",
        color="#7a4112",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#fdf5ed", edgecolor="#a35c20", lw=1.0),
        **arrow_label_font,
    )
    ax.annotate(
        "",
        xy=(11.375, 4.82),
        xytext=(11.375, 4.96),
        arrowprops=dict(arrowstyle="-|>", color="#a35c20", lw=1.8, mutation_scale=14),
    )

    card_b2 = patches.FancyBboxPatch(
        (8.15, 2.75), 6.45, 2.05, boxstyle="round,pad=0.15", ec="#a35c20", fc="#fdf5ed", lw=1.5
    )
    ax.add_patch(card_b2)
    ax.text(
        11.375,
        4.52,
        r"$\mathbf{Medium\ Loop:\ Circadian\ Stride\ (\Delta t = 24\,\mathrm{h})}$",
        ha="center",
        color="#7a4112",
        **card_title_font,
    )
    b2_text = (
        r"$\bullet$ Holling Type II saturating herbivory & grazing trauma"
        "\n"
        r"$\bullet$ Circadian basal metabolic upkeep & depletion"
        "\n"
        r"$\bullet$ Starvation culling & integer casualty clearing"
        "\n"
        r"$\bullet$ Charnov MVT patch departure checks"
        "\n"
        r"$\bullet$ Herbivore mitosis & swarm bifurcation"
    )
    ax.text(8.33, 3.52, b2_text, va="center", **bullet_font)

    ax.plot([11.375, 11.375], [2.73, 2.58], color="#2f6f5e", lw=1.8)
    ax.text(
        11.375,
        2.42,
        r"$\mathbf{7\times\ Diurnal\ Cycles}\ (\mathrm{Weekly\ Cohort\ Synchronisation})$",
        ha="center",
        va="center",
        color="#1e4d40",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#eef4f2", edgecolor="#2f6f5e", lw=1.0),
        **arrow_label_font,
    )
    ax.annotate(
        "",
        xy=(11.375, 2.12),
        xytext=(11.375, 2.26),
        arrowprops=dict(arrowstyle="-|>", color="#2f6f5e", lw=1.8, mutation_scale=14),
    )

    card_b3 = patches.FancyBboxPatch(
        (8.15, 0.50), 6.45, 1.60, boxstyle="round,pad=0.15", ec="#2f6f5e", fc="#eef4f2", lw=1.5
    )
    ax.add_patch(card_b3)
    ax.text(
        11.375,
        1.82,
        r"$\mathbf{Slow\ Loop:\ Weekly\ Stride\ (\Delta t = 168\,\mathrm{h})}$",
        ha="center",
        color="#1e4d40",
        **card_title_font,
    )
    b3_text = (
        r"$\bullet$ Vegetative growth via $168$ phase-staggered cohorts"
        "\n"
        r"$\bullet$ Cohort index $(i\ \mathrm{mod}\ 168 = t\ \mathrm{mod}\ 168)$ cuts write traffic $168\times$"
        "\n"
        r"$\bullet$ Polar seed dispersal & colonisation on $\mathbb{T}^2$"
        "\n"
        r"$\bullet$ Mycorrhizal topology & establishment tax $\delta_E^{\mathrm{tax}}$"
    )
    ax.text(8.33, 1.08, b3_text, va="center", **bullet_font)

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    png_path = output_dir / "fig05_operator_splitting_pipeline.png"
    pdf_path = output_dir / "fig05_operator_splitting_pipeline.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 5: {png_path} and {pdf_path}")


def generate_figure_6(output_dir: Path) -> None:
    """Generate Figure 6: Analytical Synthesis Delay Boundaries and Hopf Bifurcation Surface."""
    _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.2, 7.4), dpi=300)

    # =========================================================================
    # PANEL (A): Analytical Synthesis Delay Boundaries theta_crit(E_0, N_swarm)
    # =========================================================================
    e_min = 10.0
    a = 0.06
    t_h = 0.30
    e0_vals = np.linspace(10.5, 100.0, 400)

    def theta_crit_exact(e0: np.ndarray, n: float) -> np.ndarray:
        return ((1.0 / a) * np.log(e0 / e_min) + t_h * (e0 - e_min)) / n

    theta_05 = theta_crit_exact(e0_vals, 5)
    theta_10 = theta_crit_exact(e0_vals, 10)
    theta_25 = theta_crit_exact(e0_vals, 25)

    # Plot curves (Scenario 2 calibrated: a=0.06, T_h=0.30, E_min=10.0)
    ax1.plot(e0_vals, theta_05, label=r"Low Herbivore Grazing ($N_{\mathrm{swarm}} = 5$)", color="#1b5e20", lw=3.0)
    ax1.plot(e0_vals, theta_10, label=r"Nominal Grazing Influx ($N_{\mathrm{swarm}} = 10$)", color="#e65100", lw=3.0)
    ax1.plot(e0_vals, theta_25, label=r"Outbreak Influx ($N_{\mathrm{swarm}} = 25$)", color="#b71c1c", lw=3.0)

    # Mark Scenario 2 benchmark at E_0 = 50 cal, N = 25
    th25_ex = float(theta_crit_exact(np.array([50.0]), 25)[0])
    ax1.scatter([50.0], [th25_ex], color="#b71c1c", zorder=6, s=60)
    ax1.annotate(
        rf"Prop. 2 Ref. ($E_0=50, N=25$): $\theta_{{\mathrm{{crit}}}}={th25_ex:.2f}\,\mathrm{{h}}$",
        xy=(50.0, th25_ex),
        xytext=(38.0, 3.85),
        arrowprops=dict(arrowstyle="-|>", color="#b71c1c", lw=1.6),
        fontsize=9.4,
        fontweight="bold",
        color="#b71c1c",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#b71c1c", alpha=0.94),
    )

    # Fill viable vs mortality zones for N=10 exact threshold
    ax1.fill_between(e0_vals, 0, theta_10, color="#e8f5e9", alpha=0.45, label="Viable Defence Zone ($N=10$)")
    ax1.fill_between(e0_vals, theta_10, 14.5, color="#ffebee", alpha=0.42, label="Lethal Depletion Zone ($N=10$)")

    # Shaded horizontal bands for synthesis delays
    ax1.axhspan(8.0, 12.0, facecolor="#ffcdd2", edgecolor="#c62828", alpha=0.40, linestyle="--", linewidth=1.4)
    ax1.text(
        12.0,
        10.6,
        r"$\mathbf{Unprimed\ Synthesis\ Latency:\ \theta_{\mathrm{synth}} \in [8, 12]\,\mathrm{h}}$",
        fontsize=11.0,
        fontweight="bold",
        color="#b71c1c",
        va="center",
        bbox=dict(boxstyle="round,pad=0.24", facecolor="#ffffff", edgecolor="#c62828", alpha=0.92),
    )

    ax1.axhspan(1.0, 3.0, facecolor="#c8e6c9", edgecolor="#2e7d32", alpha=0.50, linestyle="--", linewidth=1.4)
    ax1.text(
        12.0,
        2.25,
        r"$\mathbf{Primed\ Rapid\ Synthesis:\ \theta_{\mathrm{primed}} \in [1, 3]\,\mathrm{h}}$",
        fontsize=11.0,
        fontweight="bold",
        color="#1b5e20",
        va="center",
        bbox=dict(boxstyle="round,pad=0.24", facecolor="#ffffff", edgecolor="#2e7d32", alpha=0.92),
    )

    # Callout annotation for critical threshold
    ax1.annotate(
        r"Fatal Depletion ($\theta > \theta_{\mathrm{crit}}$)"
        "\n"
        r"Host dies before toxin deployment",
        xy=(62.0, 8.8),
        xytext=(55.0, 6.2),
        arrowprops=dict(arrowstyle="-|>", color="#b71c1c", lw=2.0),
        fontsize=9.6,
        fontweight="bold",
        color="#b71c1c",
        bbox=dict(boxstyle="round,pad=0.26", facecolor="#ffffff", edgecolor="#b71c1c", lw=1.2),
    )

    ax1.set_xlim(10, 100)
    ax1.set_ylim(0, 14.5)
    ax1.set_xlabel(r"Initial Host Metabolic Reserve $E_0\ (\mathrm{cal})$", fontsize=14.0, fontweight="bold")
    ax1.set_ylabel(r"Synthesis Latency $\theta\ (\mathrm{hours}\ /\ \mathrm{ticks})$", fontsize=14.0, fontweight="bold")
    ax1.set_title(
        r"(a) Exact Critical Delay $\theta_{\mathrm{crit}}$ ($a=0.06, T_h=0.30, E_{\min}=10$)",
        fontsize=14.0,
        fontweight="bold",
        color="#1a237e",
        pad=12,
    )
    ax1.legend(loc="upper right", fontsize=9.8, framealpha=0.95)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.tick_params(axis="both", which="major", labelsize=12.0)

    # =========================================================================
    # PANEL (B): Emergent Limit Cycle & Hopf Bifurcation in (E_flora, N_herb)
    # =========================================================================
    r = 0.02
    k = 100.0
    m_herb = 0.02
    e_eff = 0.60
    a_dyn = 0.002
    th_dyn = 7.5

    # Nullclines
    e_range = np.linspace(6.0, 95.0, 300)
    n_null = (r * (1.0 - e_range / k) * (1.0 + a_dyn * th_dyn * e_range)) / a_dyn
    e_star = m_herb / (a_dyn * (e_eff - m_herb * th_dyn))
    n_star = (r * (1.0 - e_star / k) * (1.0 + a_dyn * th_dyn * e_star)) / a_dyn

    # Plot Nullclines
    ax2.plot(
        e_range,
        n_null,
        label=r"Flora Nullcline $\dot{E}_{\mathrm{flora}} = 0$",
        color="#2e7d32",
        lw=2.6,
        linestyle="--",
    )
    ax2.axvline(
        e_star, label=r"Herbivore Nullcline $\dot{N}_{\mathrm{herb}} = 0$", color="#c62828", lw=2.6, linestyle="--"
    )
    ax2.scatter([e_star], [n_star], color="#1a237e", s=110, zorder=5, label=r"Equilibrium $(E^*, N^*) = (22.2, 10.4)$")

    # Generate vector field
    e_grid, n_grid = np.meshgrid(np.linspace(6, 92, 16), np.linspace(1, 24, 16))
    de = r * e_grid * (1.0 - e_grid / k) - (a_dyn * e_grid * n_grid) / (1.0 + a_dyn * th_dyn * e_grid)
    dn = e_eff * (a_dyn * e_grid * n_grid) / (1.0 + a_dyn * th_dyn * e_grid) - m_herb * n_grid
    norm = np.hypot(de, dn) + 1e-6
    ax2.quiver(e_grid, n_grid, de / norm, dn / norm, color="#90a4ae", alpha=0.45, scale=24, width=0.003)

    # Fixed-step RK4 solver for the Delayed Rosenzweig-MacArthur DDE
    def solve_dde(tau: float, t_end: float, y0: tuple[float, float], dt: float = 0.25) -> np.ndarray:
        steps = int(t_end / dt)
        lag_steps = max(1, int(round(tau / dt)))
        hist = np.zeros((steps + lag_steps + 1, 2), dtype=np.float64)
        hist[: lag_steps + 1] = y0

        def rhs(curr: np.ndarray, delayed: np.ndarray) -> np.ndarray:
            e_c, n_c = curr
            e_d, _n_d = delayed
            intake_c = (a_dyn * e_c * n_c) / (1.0 + a_dyn * th_dyn * e_c)
            intake_d = (a_dyn * e_d * n_c) / (1.0 + a_dyn * th_dyn * e_d)
            return np.array([r * e_c * (1.0 - e_c / k) - intake_c, e_eff * intake_d - m_herb * n_c])

        for idx in range(lag_steps, steps + lag_steps):
            y_c = hist[idx]
            y_d = hist[idx - lag_steps]
            y_d_half = 0.5 * (hist[idx - lag_steps] + hist[idx - lag_steps + 1])
            y_d_next = hist[idx - lag_steps + 1]
            k1 = rhs(y_c, y_d)
            k2 = rhs(y_c + 0.5 * dt * k1, y_d_half)
            k3 = rhs(y_c + 0.5 * dt * k2, y_d_half)
            k4 = rhs(y_c + dt * k3, y_d_next)
            hist[idx + 1] = np.maximum(1e-3, y_c + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4))
        return hist[lag_steps:]

    # Trajectory 1: Damped Focus (Subcritical delay tau = 0.50 h < tau* = 2.38 h)
    sol_damped = solve_dde(tau=0.50, t_end=3800.0, y0=(31.0, 8.2))
    ax2.plot(
        sol_damped[:, 0],
        sol_damped[:, 1],
        color="#1565c0",
        lw=2.2,
        linestyle="-.",
        label=r"Damped Focus ($\tau = 0.5\,\mathrm{h} < \tau^*$, Point Attractor)",
    )

    # Trajectory 2: Limit cycle attractor (Supercritical delay tau = 4.00 h > tau* = 2.38 h)
    sol_limit = solve_dde(tau=4.00, t_end=9000.0, y0=(26.0, 9.8))
    orbit_tail = sol_limit[-2200:]
    orbit_e = orbit_tail[:, 0]
    orbit_n = orbit_tail[:, 1]
    ax2.plot(
        orbit_e,
        orbit_n,
        color="#d84315",
        lw=3.0,
        label=r"Stable Limit Cycle ($\tau = 4.0\,\mathrm{h} > \tau^*$, DDE Orbit)",
    )

    # Add directional arrows on limit cycle
    for idx in [150, 550, 950, 1350]:
        ax2.annotate(
            "",
            xy=(orbit_e[idx + 6], orbit_n[idx + 6]),
            xytext=(orbit_e[idx], orbit_n[idx]),
            arrowprops=dict(arrowstyle="-|>", color="#d84315", lw=2.6, mutation_scale=16),
        )

    # Callout annotation for Hopf bifurcation
    ax2.text(
        33.0,
        19.8,
        "Poincaré-Andronov-Hopf Bifurcation\n"
        r"$\bullet$ Critical search lag: $\tau^* = 2.38\,\mathrm{h}$ ($\alpha = -5.56{\times}10^{-4} < 0$)"
        "\n"
        r"$\bullet$ Continuous DDE ($dt=0.25\,\mathrm{h},\ \tau^* > \Delta t = 1\,\mathrm{h}$)"
        "\n"
        r"$\bullet$ Bounded cycle attractor: $\mathcal{A}_{\mathrm{orbit}} \subset \mathbb{R}_+^2$",
        fontsize=10.4,
        fontweight="bold",
        color="#1a237e",
        bbox=dict(boxstyle="round,pad=0.32", facecolor="#ffffff", edgecolor="#3949ab", lw=1.2, alpha=0.95),
    )

    ax2.set_xlim(4, 95)
    ax2.set_ylim(1, 25)
    ax2.set_xlabel(r"Flora Metabolic Biomass $E_{\mathrm{flora}}\ (\mathrm{cal})$", fontsize=14.0, fontweight="bold")
    ax2.set_ylabel(r"Herbivore Swarm Headcount $N_{\mathrm{herb}}$", fontsize=14.0, fontweight="bold")
    ax2.set_title(
        "(b) Emergent Limit Cycle via Spatial Search Lag Delay",
        fontsize=14.8,
        fontweight="bold",
        color="#1a237e",
        pad=12,
    )
    ax2.legend(loc="lower right", fontsize=10.5, framealpha=0.95)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.tick_params(axis="both", which="major", labelsize=12.0)

    plt.subplots_adjust(left=0.06, right=0.98, top=0.93, bottom=0.10, wspace=0.16)
    png_path = output_dir / "fig06_limit_cycle_bifurcation.png"
    pdf_path = output_dir / "fig06_limit_cycle_bifurcation.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 6: {png_path} and {pdf_path}")


def generate_figure_7(output_dir: Path) -> None:
    """Generate Figure 7: Ecotone 10-Seed Coexistence, Wind Ablation & CRN Sobol GSA."""
    eco_dir = Path(__file__).resolve().parents[2] / "docs" / "latex" / "scientific_report" / "data" / "ecotone_256x256"
    batch = json.loads((eco_dir / "batches/ecotone_trial2_10seed_summary.json").read_text())
    ablation_summary = json.loads((eco_dir / "results/ablation_256x256_summary.json").read_text())["summary"]
    sobol_128 = json.loads((eco_dir / "results/sobol_128x64_n256_t1500.json").read_text())
    sobol_256 = json.loads((eco_dir / "results/sobol_256x256_n32_t1000.json").read_text())

    t = np.array(batch["ticks"], dtype=np.float64)
    n_ticks = len(t)
    grid_area = 256.0 * 256.0
    e_mean = np.array(batch["total_flora_energy_mean"], dtype=np.float64) / 1e6  # Mcal
    e_sd = np.array(batch["total_flora_energy_std"], dtype=np.float64) / 1e6
    occ_mean = 100.0 * np.array(batch["flora_population_mean"], dtype=np.float64) / grid_area
    occ_sd = 100.0 * np.array(batch["flora_population_std"], dtype=np.float64) / grid_area

    flora_arr = np.column_stack([np.array(batch["per_flora_pop_mean"][str(i)], dtype=np.float64) for i in range(6)])
    herb_arr = np.column_stack([np.array(batch["per_herbivore_pop_mean"][str(i)], dtype=np.float64) for i in range(5)])

    def _shannon_series(counts: np.ndarray, n_sp: int) -> np.ndarray:
        tot = np.maximum(1.0, counts.sum(axis=1, keepdims=True))
        props = np.clip(counts / tot, 1e-9, 1.0)
        return -np.sum(props * np.log(props), axis=1) / np.log(float(n_sp))

    j_flora_t = _shannon_series(flora_arr, 6)
    j_herb_t = _shannon_series(herb_arr, 5)

    _fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15.4, 8.8), dpi=300)
    title_font = {"fontsize": 12.2, "fontweight": "bold", "color": "#1a237e"}
    label_font = {"fontsize": 10.8, "fontweight": "bold"}
    tick_font = 9.8

    # (a) 10-Seed 256x256 Aggregate Flora Reserve & Lattice Occupancy
    ax1.fill_between(
        t,
        np.maximum(0.0, e_mean - e_sd),
        e_mean + e_sd,
        color="#a5d6a7",
        alpha=0.45,
        label=r"Flora Reserve $\pm 1\,\mathrm{SD}$",
    )
    l_e = ax1.plot(t, e_mean, color="#1b5e20", lw=2.3, label=r"Aggregate Flora Reserve $E_{\mathrm{tot}}$ (Mcal)")
    ax1.set_xlim(0, n_ticks)
    ax1.set_ylim(0.0, 3.25)
    ax1.set_xlabel("Simulation Horizon (Hours / Ticks)", **label_font)
    ax1.set_ylabel("Flora Metabolic Reserve (Mcal)", **label_font, color="#1b5e20")
    ax1.set_title("(a) 10-Seed 256x256 Flora Reserve & Lattice Occupancy", **title_font, pad=7)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.tick_params(axis="both", labelsize=tick_font)
    ax1.tick_params(axis="y", colors="#1b5e20")

    ax1_twin = ax1.twinx()
    ax1_twin.fill_between(
        t,
        np.maximum(0.0, occ_mean - occ_sd),
        occ_mean + occ_sd,
        color="#b2dfdb",
        alpha=0.35,
    )
    l_o = ax1_twin.plot(
        t, occ_mean, color="#00695c", lw=2.0, linestyle="--", label=r"Lattice Occupancy Mean $\pm 1\,\mathrm{SD}$ (%)"
    )
    ax1_twin.set_ylim(0.0, 58.0)
    ax1_twin.set_ylabel("Lattice Occupancy (%)", fontsize=10.5, fontweight="bold", color="#00695c")
    ax1_twin.tick_params(axis="y", labelsize=tick_font, colors="#00695c")

    lines1, labs1 = ax1.get_legend_handles_labels()
    lines1t, labs1t = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines1t, labs1 + labs1t, loc="upper left", fontsize=8.4, framealpha=0.94)
    ax1.text(
        1880,
        0.24,
        "10/10 Full 11-Species Persistence (KM = 1.00)\n"
        r"Tick 4000 Occ. Med: $46.85\%$ (IQR $46.62\text{-}47.11\%$)",
        fontsize=8.3,
        fontweight="bold",
        color="#1a237e",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#2e7d32", lw=0.9, alpha=0.93),
    )

    # (b) Multi-Guild Herbivore Headcounts & Shannon Equitability J(t)
    h_meta = [
        (0, r"$h_0$ L. dispar", "#1565c0", "-"),
        (1, r"$h_1$ P. vitellinae", "#00838f", "-"),
        (2, r"$h_2$ A. pisum", "#ef6c00", "-"),
        (3, r"$h_3$ N. pronuba", "#c62828", "-"),
        (4, r"$h_4$ P. brassicae", "#6d4c41", "-"),
    ]
    for hid, hlab, hcol, hls in h_meta:
        ax2.plot(t, herb_arr[:, hid], color=hcol, lw=1.7, ls=hls, label=hlab)
    ax2.set_xlim(0, n_ticks)
    ax2.set_ylim(0, 6200)
    ax2.set_xlabel("Simulation Horizon (Hours / Ticks)", **label_font)
    ax2.set_ylabel("Mean Guild Headcount", **label_font)
    ax2.set_title("(b) Herbivore Guild Trajectories & Shannon Equitability", **title_font, pad=7)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.tick_params(axis="both", labelsize=tick_font)

    ax2_twin = ax2.twinx()
    ax2_twin.plot(t, j_herb_t, color="#4a148c", lw=2.1, ls="--", label=r"$J_{\mathrm{herb}}(t)$")
    ax2_twin.plot(t, j_flora_t, color="#2e7d32", lw=2.0, ls=":", label=r"$J_{\mathrm{flora}}(t)$")
    ax2_twin.set_ylim(0.50, 1.10)
    ax2_twin.set_ylabel(r"Shannon Equitability $J(t)$", fontsize=10.5, fontweight="bold", color="#4a148c")
    ax2_twin.tick_params(axis="y", labelsize=tick_font, colors="#4a148c")

    l2_1, lab2_1 = ax2.get_legend_handles_labels()
    l2_2, lab2_2 = ax2_twin.get_legend_handles_labels()
    ax2_twin.legend(
        l2_1 + l2_2,
        lab2_1 + lab2_2,
        loc="upper left",
        fontsize=7.9,
        ncol=2,
        framealpha=0.94,
        facecolor="#ffffff",
        edgecolor="#cbd5e1",
    )
    ax2.text(
        2150,
        5250,
        r"Med $J_{\mathrm{herb}}(4000)=0.842$, $J_{\mathrm{flora}}=0.721$",
        fontsize=8.2,
        fontweight="bold",
        color="#4a148c",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#4a148c", lw=0.8, alpha=0.93),
    )

    # (c) 90-Run Wind & Dual-Channel Ablation (256x256)
    winds = np.array(sorted({row["wind_speed"] for row in ablation_summary}), dtype=np.float64)

    def _ab_series(tr: str, key: str) -> np.ndarray:
        by_w = {r["wind_speed"]: r[key] for r in ablation_summary if r["treatment"] == tr}
        return np.array([float(by_w[float(w)]) for w in winds], dtype=np.float64)

    for tr, lab, fmt, col in (
        ("fully_ablated", "Fully Ablated (No Signalling/Toxins)", "-s", "#c62828"),
        ("cmn_severed", "CMN-Severed (Airborne VOCs Only)", "-^", "#ef6c00"),
        ("intact", "Intact Dual-Channel (VOC + CMN)", "-o", "#1b5e20"),
    ):
        ax3.errorbar(
            winds,
            _ab_series(tr, "herb_deaths_mean"),
            yerr=_ab_series(tr, "herb_deaths_se"),
            fmt=fmt,
            color=col,
            lw=2.1,
            markersize=5.5,
            capsize=3.5,
            label=lab,
        )
    ax3.fill_between(
        winds,
        _ab_series("intact", "herb_deaths_mean"),
        _ab_series("cmn_severed", "herb_deaths_mean"),
        color="#ffe0b2",
        alpha=0.55,
    )
    ax3.set_xlim(-0.10, 2.10)
    ax3.set_ylim(3800, 20500)
    ax3.set_xlabel(
        r"Effective Plume Drift $\|\mathbf{u}_{\mathrm{wind}}\|\ (\mathrm{cells/tick},\ \mathrm{WSW}\to\mathrm{ENE})$",
        **label_font,
    )
    ax3.set_ylabel("Cumulative Grazing Plant Deaths", **label_font)
    ax3.set_title("(c) Dual-Channel Wind Ablation (256x256, 90 Runs)", **title_font, pad=7)
    ax3.grid(True, linestyle=":", alpha=0.6)
    ax3.tick_params(axis="both", labelsize=tick_font)
    ax3.legend(loc="upper left", fontsize=8.1, framealpha=0.94, ncol=1)

    # Inset contrasting mycorrhizal p0 vs non-mycorrhizal p5 at u=0.50 & 1.25 m/s
    ins = ax3.inset_axes([0.36, 0.31, 0.60, 0.34])
    cats = [r"$p_0$ @ $0.5$", r"$p_0$ @ $1.25$", r"$p_5$ @ $0.5$", r"$p_5$ @ $1.25$"]
    x_i = np.arange(len(cats))
    int_vals = [
        float(
            next(r["killed_p0_mean"] for r in ablation_summary if r["treatment"] == "intact" and r["wind_speed"] == 0.5)
        ),
        float(
            next(
                r["killed_p0_mean"] for r in ablation_summary if r["treatment"] == "intact" and r["wind_speed"] == 1.25
            )
        ),
        float(
            next(r["killed_p5_mean"] for r in ablation_summary if r["treatment"] == "intact" and r["wind_speed"] == 0.5)
        ),
        float(
            next(
                r["killed_p5_mean"] for r in ablation_summary if r["treatment"] == "intact" and r["wind_speed"] == 1.25
            )
        ),
    ]
    sev_vals = [
        float(
            next(
                r["killed_p0_mean"]
                for r in ablation_summary
                if r["treatment"] == "cmn_severed" and r["wind_speed"] == 0.5
            )
        ),
        float(
            next(
                r["killed_p0_mean"]
                for r in ablation_summary
                if r["treatment"] == "cmn_severed" and r["wind_speed"] == 1.25
            )
        ),
        float(
            next(
                r["killed_p5_mean"]
                for r in ablation_summary
                if r["treatment"] == "cmn_severed" and r["wind_speed"] == 0.5
            )
        ),
        float(
            next(
                r["killed_p5_mean"]
                for r in ablation_summary
                if r["treatment"] == "cmn_severed" and r["wind_speed"] == 1.25
            )
        ),
    ]
    ins.bar(x_i - 0.18, int_vals, width=0.35, color="#1b5e20", label="Intact")
    ins.bar(x_i + 0.18, sev_vals, width=0.35, color="#ef6c00", label="CMN-Sev.")
    ins.set_xticks(x_i)
    ins.set_xticklabels(cats, fontsize=7.2)
    ins.tick_params(axis="y", labelsize=7.0)
    ins.set_title(r"Mycorrhizal $p_0$ vs. Non-CMN $p_5$ Deaths", fontsize=7.6, fontweight="bold", pad=2)
    ins.grid(True, axis="y", linestyle=":", alpha=0.5)
    ins.legend(loc="upper right", fontsize=6.8, framealpha=0.9)

    # (d) Converged CRN Sobol GSA (128x64 N=1,792 & 256x256 N=224 Cross-Check)
    f_names = [f[0] for f in sobol_128["factors"]]
    label_map = {
        "consumption_rate_mult": r"Consumption ($a_{\mathrm{feed}}$)",
        "energy_min_mult": r"Starvation ($E_{\min}$)",
        "defense_cmn_cost_mult": r"Defence / CMN Cost",
        "wind_magnitude": r"Wind Speed ($\|\mathbf{u}\|$)",
        "p4_camo_repellent_strength": r"$p_4$ Camo / Repellent",
    }
    res_128 = sobol_128["outputs"]["mean_flora_reserve"]
    herb_128 = sobol_128["outputs"]["terminal_herb_heads"]
    res_256 = sobol_256["outputs"]["mean_flora_reserve"]

    order = np.argsort(res_128["ST"])
    y_pos = np.arange(len(order))
    sorted_labels = [label_map[f_names[i]] for i in order]

    s1_e = np.maximum(0.0, np.array(res_128["S1"])[order])
    st_e = np.array(res_128["ST"])[order]
    err_lo = np.maximum(0.0, st_e - np.array(res_128["ST_ci_low"])[order])
    err_hi = np.maximum(0.0, np.array(res_128["ST_ci_high"])[order] - st_e)
    st_h = np.array(herb_128["ST"])[order]
    st_256 = np.array(res_256["ST"])[order]

    bh = 0.25
    ax4.barh(y_pos + bh, st_h, height=bh, color="#5e35b1", alpha=0.86, label=r"$S_T$ Herbivore Heads ($128{\times}64$)")
    ax4.barh(
        y_pos,
        st_e,
        height=bh,
        xerr=[err_lo, err_hi],
        capsize=3,
        color="#1565c0",
        alpha=0.90,
        label=r"$S_T$ Flora Reserve ($\pm 95\%$ CI)",
    )
    ax4.barh(y_pos - bh, s1_e, height=bh, color="#26a69a", alpha=0.90, label=r"$S_1$ Flora Reserve (Centred)")
    ax4.scatter(
        st_256,
        y_pos,
        marker="D",
        s=42,
        color="#ff6f00",
        edgecolor="#212121",
        zorder=5,
        label=r"$S_T$ Flora Reserve ($256{\times}256$, $N{=}224$)",
    )

    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(sorted_labels, fontsize=9.2, fontweight="bold")
    ax4.set_xlim(0.0, 1.05)
    ax4.set_xlabel(r"CRN Sobol Sensitivity Index ($N{=}1{,}792$ Primary + $224$ Cross-Check)", **label_font)
    ax4.set_title("(d) CRN Sobol Sensitivity & Spatial Scale Comparison", **title_font, pad=7)
    ax4.legend(loc="lower right", fontsize=8.0, framealpha=0.94)
    ax4.grid(True, axis="x", linestyle=":", alpha=0.6)
    ax4.tick_params(axis="x", labelsize=tick_font)
    ax4.text(
        0.52,
        1.78,
        rf"Reserve: $\sum S_1={sum(res_128['S1']):.3f}$, $\sum S_T={sum(res_128['ST']):.3f}$"
        "\n"
        rf"Herbivores: $\sum S_1={sum(herb_128['S1']):.3f}$, $\sum S_T={sum(herb_128['ST']):.3f}$",
        fontsize=8.0,
        fontweight="bold",
        color="#1a237e",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="#ffffff", edgecolor="#1565c0", lw=0.9, alpha=0.93),
    )

    plt.subplots_adjust(left=0.06, right=0.95, top=0.94, bottom=0.08, hspace=0.33, wspace=0.45)
    png_path = output_dir / "fig07_multispecies_coexistence.png"
    pdf_path = output_dir / "fig07_multispecies_coexistence.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 7: {png_path} and {pdf_path}")


def generate_figure_8(output_dir: Path) -> None:
    """Generate Figure 8: 4-Panel Light-Mode Live Web-UI Collage from Ecotone Showcase."""
    panels_dir = output_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    im1_path = panels_dir / "fig08a_live_spatial_grid.png"
    im2_path = panels_dir / "fig08b_cell_diagnostics.png"
    im3_path = panels_dir / "fig08c_config_diet_triggers.png"
    im4_path = panels_dir / "fig08d_live_telemetry_export.png"

    missing = [p for p in (im1_path, im2_path, im3_path, im4_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing live Web-UI panel captures for Figure 8: {missing}")

    im1 = plt.imread(str(im1_path))
    im2 = plt.imread(str(im2_path))
    im3 = plt.imread(str(im3_path))
    im4 = plt.imread(str(im4_path))

    _fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15.2, 8.9), dpi=300)

    panels = [
        (ax1, im1, "(a) Live 256 x 256 Ecotone Spatial Renderer (Tick 331)"),
        (ax2, im2, "(b) Local Cell Inspector: Salix purpurea & Phratora vitellinae"),
        (ax3, im3, "(c) Fixed 16-Channel Trophic Diet Matrix (5 x 6 Ecotone)"),
        (ax4, im4, "(d) Live Lotka-Volterra Telemetry, Defence Ratio & Export Suite"),
    ]
    for ax_p, img_p, title_p in panels:
        ax_p.imshow(img_p)
        ax_p.set_xticks([])
        ax_p.set_yticks([])
        for spine in ax_p.spines.values():
            spine.set_edgecolor("#cbd5e1")
            spine.set_linewidth(0.9)
        ax_p.set_title(title_p, fontsize=11.8, fontweight="bold", color="#1a237e", pad=6)

    plt.subplots_adjust(left=0.012, right=0.988, top=0.955, bottom=0.012, wspace=0.035, hspace=0.095)
    png_path = output_dir / "fig08_runtime_architecture_ui.png"
    pdf_path = output_dir / "fig08_runtime_architecture_ui.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Generated Figure 8: {png_path} and {pdf_path}")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parents[2] / "docs" / "latex" / "scientific_report" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_figure_6(out_dir)
    generate_figure_7(out_dir)
    if (out_dir / "panels" / "fig08a_live_spatial_grid.png").exists():
        generate_figure_8(out_dir)
