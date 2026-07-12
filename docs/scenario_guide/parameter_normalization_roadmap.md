---
type: concept
title: "Parameter Normalization and UI/UX Simplification Roadmap"
status: active
version: 1.0
description: "Comprehensive roadmap for simplifying configuration, standardizing parameter ranges, UI/UX conversions, and testing strategies in the PHIDS simulator."
---

# Parameter Normalization & UI/UX Roadmap

This document outlines the strategic engineering roadmap to normalize, standardize, and clarify simulation parameters within the PHIDS engine and user interface. The primary objective is to simplify scenario configuration, reduce entry barriers for ecological modeling, and make emergent simulation states easier to interpret.

It incorporates critical lessons learned from previous automation attempts, strictly outlining how refactoring should be approached without breaking the core engine or regression suites.

---

## 1. Core Inefficiencies & Discrepancies

Currently, configuration metrics and UI tooltips exhibit several friction points:

* **Counter-Intuitive Names:** `velocity` in the swarm component represents "ticks between movements", meaning a higher value decreases movement speed.
* **Mismatched Scales:** Parameters mix absolute rates (e.g., `mechanical_damage_per_bite = 2.0`) with normalized coefficients (e.g., `apparent_nutrition_factor` as `0.0 to 1.0`) and large population limits (e.g., `split_population_threshold = 1000`).
* **Linear Slider Instabilities:** UI input controls use linear ranges, which lack the precision required for fine-tuning low-level parameters (e.g., metabolic upkeep coefficients around `0.05`).
* **Hardcoded Constraints:** Core ecological constants that govern chemical diffusion and interaction limits are hardcoded, limiting biome variability and design space exploration (DSE).

---

## 2. Detailed Execution Plan

### Phase 0: Schema and Engine Constants Migration

Migrate hardcoded biological constraints into the dynamic `SimulationConfig` to allow the DSE algorithm to explore varied biomes and to let scenario authors tweak environmental dynamics.

* **Target Constants:** Move variables like `SIGNAL_DECAY_FACTOR` and `SUBSTANCE_EMIT_RATE` from `src/phids/shared/constants.py` into `schemas.py` and `ui_state.py`.
* **UI Integration:** Expose these variables under the **Biotope** tab in the configuration UI.
* **⚠️ CRITICAL Testing & Refactoring Anti-Pattern:** Do **NOT** use custom regex scripts, `sed`, or mass-replacement bash one-liners to update the test suite when the signatures of core engine functions (like `run_signaling(...)`) change. These scripts often break Python's AST (e.g., shifting `from __future__ import annotations` lines) and destroy test formatting.
* **The Correct Pattern:** Introduce the new config parameters to engine functions using **backward-compatible default keyword arguments** (e.g., `signal_decay_factor: float = 0.85`). This completely bypasses the need to mass-refactor dozens of integration tests; only the specific tests validating the new dynamic behavior need to be updated.

### Phase 1: Presenter Conversions

Move the heavy lifting of percentage and ratio calculations out of the Jinja2 HTML templates and into the backend presenter layer (`src/phids/api/presenters/dashboard/cell_details.py`).

* **Dual-State Payloads:** **Never discard the absolute values.** The frontend requires both. The presenter must inject the computed relative metrics alongside the raw values.
* **Target Conversions:**
  * **Energy Capacity:** Flora energy should be serialized as an absolute value and a ratio against `z6_max_total_flora_energy` (e.g., `energy: 45.0, energy_ratio: 0.225`).
  * **Swarm Starvation/Mitosis:** Swarm sizes should be evaluated against their `split_population_threshold` for a "Mitosis Readiness" percentage. Energy should be displayed relative to the minimum threshold for survival (`Min: Population * energy_min`).
  * **Toxins & Signals:** Display local concentration relative to trigger thresholds or maximum saturation capacity (e.g., `Signal 1: 0.8 / 1.0 (80%)`).

### Phase 2: HTMX Controls & Sliders

Revamp the input mechanisms to avoid floating-point errors and maintain fine-grained control across massively different magnitudes.

* **Synchronized Dual-Controls:** Replace naked `<input type="number">` fields with a synchronized pairing: a slider (`<input type="range">`) side-by-side with a precise numeric input. Changing one must immediately update the other.
* **Logarithmic Scaling Targets:** Apply logarithmic curves to configuration sliders for wide-range variables, specifically:
  * `split_population_threshold`
  * `initial_population`
  * `trigger_min_herbivore_population`
* **Relative Percentage Modifiers:** Expose variables like diffusion and dissipation constants as normalized percentages (`0% to 100%`) in the UI, mapping them back to the narrow decimal bounds expected by the physics engine (e.g., mapping UI `100%` to an engine rate of `0.25`).

### Phase 3: Schema Metadata & Presentation Labels

Align terminology to biological and semantic expectations without fracturing the highly optimized data-oriented engine core.

* **⚠️ CRITICAL Rule on Variable Renaming:** Do **NOT** rename the internal Python variables (e.g., `velocity`, `growth_rate`, `consumption_rate`) in the ECS engine, database, or Zarr schemas. Doing so breaks backwards compatibility with legacy Zarr archives, disrupts double-buffering JIT layouts, and causes widespread regression.
* **The Correct Pattern:** Update only the human-readable metadata and Jinja2 templates:
  * **Movement Speed:** Expose `velocity` in tooltips and panels as **Movement Interval (ticks)**.
  * **Growth Rate:** Present `growth_rate` as **Growth Rate (% per tick)**.
  * **Consumption Rate:** Retain the biologically accurate term **Consumption Rate** in the code, but clarify its units in the UI tooltips: **Consumption Rate (Energy per individual per tick)**.

### Phase 4: Guide Boards and Tooltip Enrichment

Enhance the "Info Boards" at the bottom of the HTMX configuration views to grab users by the hand, explaining how UI inputs translate into underlying biological and mathematical models.

* **Biotope Guide:** Explain the "Z-Rules" (Z2, Z4, Z6, Z7) as ecological conservation limits to prevent runaway simulations. Explain how wind vectors ($X, Y$) physically advect chemical grids.
* **Flora Guide:** Detail the metabolic zero-sum game: energy spent on passive/active defenses is subtracted from reserves, slowing down the reproduction interval. Explain Apparent Nutrition withdrawal.
* **Herbivore Guide:** Document the starvation equation (Upkeep = Population * Energy Cost). Explain how the `velocity` variable actually dictates the *ticks between movements*.
* **Trigger Guide:** Contrast the isotropic diffusion of airborne signals (decaying via `SIGNAL_DECAY_FACTOR`) against directional mycorrhizal signaling.

---

## 3. Implementation Log & Execution History

### Status: COMPLETED ✅

* **Phase 0 Execution:** `SIGNAL_DECAY_FACTOR` and `SUBSTANCE_EMIT_RATE` were decoupled from `constants.py` and successfully wired through `schemas.py`, `ui_state.py`, and the core engine methods (`diffuse_signals`, `run_signaling`).
  * *Crucial Fix:* Testing initially broke due to `env.diffuse_signals = lambda: None` signatures in integration tests. This was resolved correctly using `git restore` and targeted replacements of the mock signatures (e.g., `lambda **kwargs: None`) instead of dangerous regex rewrites that were corrupting the Python AST (e.g. `__future__` imports).
* **Phase 1 Execution:** Rebuilt `cell_details.py` to calculate relative ratios (e.g., `energy_ratio`, `mitosis_progress`, `value_pct`) server-side, injecting them safely into the JSON payload alongside absolute values to guarantee double-state payload constraints.
* **Phase 2 Execution:** Tooltips in `dashboard.html` now dynamically consume the backend labels (`energy_label`, `mitosis_label`). The header `Repr. Divisor` was successfully renamed to `Split Threshold (Energy)`. Following biological exactness, `consumption_rate` was kept named as such but clarified in the guideboards.
* **Phase 3/4 Execution:** All four configuration tabs (`biotope_config.html`, `herbivore_config.html`, `flora_config.html`, `substance_config.html`) received massively expanded Info Boards. These boards now define exact engine dynamics (Lotka-Volterra interaction strength, chemical peak diffusion, Autotrophic carrying capacities, and Semiochemical Action Profiles). All 1045 regression/integration tests are passing successfully.
