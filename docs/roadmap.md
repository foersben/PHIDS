---
type: roadmap
title: Strategic Multi-Phase Development Roadmap
status: active
version: 1.4
description: Comprehensive, multi-stage development roadmap for PHIDS, detailing biological fidelity milestones, computational complexity, full-stack implementation changes (backend, UI, ETL database), direct Zarr telemetry updates, QA & benchmark gates, PyInstaller packaging, and DSE parameter scope extensions.
tags:
- phids
- roadmap
- architecture
- biological-fidelity
- hpc
- ecs
- htmx
- dse
- zarr
- pyinstaller
timestamp: "2026-07-26T01:30:00Z"
resources:
- docs/scientific_model/index.md
- docs/technical_architecture/system_architecture.md
- docs/scenario_guide/design_space_exploration.md
- docs/scenario_guide/empirical_database.md
---

This document defines the multi-phase strategic development roadmap for the Plant-Herbivore Interaction & Defense Simulator (PHIDS). It details realized and planned milestones across **biological fidelity**, **full-stack software architecture**, **empirical database ingestion**, **UI controls**, **telemetry/replay updates**, **QA regression gates**, and **high-performance computing (HPC)** perspectives.

---

### Core Architectural Principles

1. **Standalone Scientific Utility**: Every milestone is partitioned into self-contained, independent sub-stages (v2.1, v2.2, etc.). Completing any single sub-stage yields an immediately usable, scientifically validated capability for ecological researchers, requiring zero reliance on subsequent stages.
2. **Zero-Overhead Opt-In Guarantee**: Optional biological and environmental systems (e.g., soil chemistry, weather profiles, 3D grids) default to disabled ($0\text{ bytes}$ allocated, $0\text{ ms}$ CPU overhead). They can be selectively loaded via scenario YAML/JSON files.
3. **Clean Unencumbered Evolution Strategy (No Backward Compatibility)**: PHIDS explicitly rejects backward-compatibility shims, legacy schema fallbacks, or versioned dataset wrappers. Because the framework is in active pre-release development prior to formal academic deployment, data models, Zarr telemetry buffers, and scenario schemas evolve cleanly. When breaking updates occur, example scenario files (`scenarios/*.yaml`), benchmark suites, and tests are updated directly to the latest specification.
4. **Full-Stack End-to-End Scope**: Each sub-stage plans all necessary modifications across the Python backend, Jinja2/HTMX web UI, scenario import/export buttons, DuckDB empirical database ETL, Zarr telemetry schemas, PyInstaller packaging, and Design Space Exploration (DSE) parameter search spaces.
5. **Quality & Regression Gates**: Every sub-stage must pass strict QA gates, including mutation testing via `mutmut` ($>85\%$ kill rate) and performance regression gates via `pytest-benchmark` ($<5\%$ tick latency regression).
6. **Deterministic PRNG Seeding**: All stochastic events (seed flight, zoochory transport, weather noise) use per-component/per-region PRNG generators (`np.random.Generator`), ensuring tick-by-tick deterministic replay capability.

---

## Phase 1: High-Performance Engine & Core Biological Upgrades (v1.0 - Realized)

### Realized Biological & Computer Science Milestones

* **Data-Oriented ECS Architecture & Flow Fields** `[Realized]`: Unified spatial hashing with zero-allocation JIT execution loops ($F = \alpha E \cdot N - \beta \sum T_k$).
* **Continuous Sigmoidal Hill Priming** `[Realized]`: Transitioned VOC perception from step-functions to dose-dependent logarithmic Hill kinetics ($S(c) = \frac{c^n}{K^n + c^n}$).
* **Rate-Limited Phloem Translocation** `[Realized]`: Modeled vascular carbohydrate movement from leaves to roots ($\frac{dN}{dt} = -k(N - N_{\text{target}})$).
* **Constitutive Morphological Defenses** `[Realized]`: Integrated mechanical mouthpart damage ($\lfloor m_{\text{bite}} (1-\rho) \rfloor$) and cell-wall caloric discounting ($\eta_{\text{net}}$).
* **Holling Type II Response & Swarm Paradigms** `[Realized]`: Implemented saturating feeding curves with handling time $T_h$ and multi-tier flight behavior (`MACRO_SWARM`, `SOLITARY_GRAZER`, `OVIPOSITION_SEEKER`).
* **Operator-Splitting PDE Solvers & Telemetry** `[Realized]`: Combined semi-Lagrangian wind advection with $3\times 3$ Gaussian stencils, Zarr telemetry, and HTMX web visualization.

---

## Phase 2: Advanced Spatial Fidelity & Micro-Climate Extensions (v2.0 - Planned)

Phase 2 is structured into granular, independent sub-stages. Each sub-stage can be implemented, tested, and published independently.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               PHIDS PHASE 2 SUB-STAGE ROADMAP                                   │
├─────────────────┬─────────────────┬──────────────────┬─────────────────┬────────────────────────┤
│  Sub-Stage 2.1  │  Sub-Stage 2.2  │  Sub-Stage 2.3   │  Sub-Stage 2.4  │  Sub-Stage 2.5 & 2.6   │
│  Soil Seed Bank │  Zoochory       │  Trait-Based     │  Soil Detritus  │  Weather Profiles &    │
│  & Dormancy     │  Dispersal      │  State Machines  │  & Recycling    │  3D Vertical Canopy    │
└─────────────────┴─────────────────┴──────────────────┴─────────────────┴────────────────────────┘
```

---

### Sub-Stage 2.1: Soil Seed Bank & Dormancy Kinetics (v2.1)

* **Biological Target**: Replace instant adult plant spawning with a persistent soil seed bank. Dispersed seeds land in a dormant state (`seed_bank_layer`) and require accumulated thermal degree-days ($GDD = \sum \max(0, T - T_{\text{base}})$) and a moisture threshold ($W > W_{\text{germ}}$) to sprout.
* **Standalone Researcher Utility**: Enables plant ecologists to study seed longevity, seasonal germination windows, seed mortality, and weed bank dynamics without requiring subterranean soil chemistry or weather layers.
* **Computational & Performance Cost**:
  * **Memory**: $+4\text{ Bytes/cell}$ float32 seed density array ($\sim 1\text{ MB}$ for a $512 \times 512$ grid).
  * **CPU Latency**: $< 0.05\text{ ms/tick}$ via vectorized Numba JIT array updates.
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Add `SeedBankConfig` schema to `phids.api.schemas.simulation`, create `seed_bank_layer` in `GridEnvironment`, update `DraftState`/`DraftService` for hot-reloading, and integrate germination triggers in `lifecycle.py` ($\sim 250$ LOC).
  * **UI & Dashboard**: Add a "Seed Bank & Dormancy" toggle card in `src/phids/api/templates/index.html`, GDD threshold sliders, scenario JSON export/import bindings, and a live "Seed Bank Heatmap" layer toggle in the web dashboard renderer.
  * **Empirical Bio-Database Pipeline**: Extend DuckDB schema (`phids.analytics.bio_database`) and `src/data_pipeline/json_builder.py` to ingest `germination_gdd_threshold` and `seed_decay_rate` from the TRY database.
  * **Telemetry & Replay Schema**: Direct update to `ReplayState` and Zarr dataset schemas to serialize `seed_bank_density`. All scenario examples (`scenarios/*.yaml`) updated to match.
  * **QA & Verification Gates**: Unit tests for $GDD$ accumulation; mutation test coverage via `mutmut` ($>85\%$ kill rate on `lifecycle.py`); benchmark regression gate ($<5\%$ tick overhead).
  * **Packaging**: Verify standalone binary bundling in `packaging/phids.spec` for updated templates and DuckDB schemas.
  * **Documentation**: Update `docs/technical_architecture/engine_execution.md` (lifecycle phase update) and `docs/scenario_guide/index.md`.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#1-sub-stage-21-soil-seed-bank--dormancy) for new continuous genes (`germination_gdd_threshold`, `seed_dormancy_decay_rate`).

---

### Sub-Stage 2.2: Multi-Vector Seed Dispersal & Zoochory (v2.2)

* **Biological Target**: Expand seed dispersal beyond wind (anemochory) to animal-mediated transport (zoochory). Grazing herbivores ingesting reproductive plants transport seeds internally or on their bodies, releasing them along migration paths via frass/droppings.
* **Standalone Researcher Utility**: Allows landscape ecologists to model invasive plant spread along herbivore corridors and animal-mediated seed shadow patterns independently of soil chemistry.
* **Computational & Performance Cost**:
  * **Memory**: $0$ additional grid arrays (uses existing `SwarmComponent` fields).
  * **CPU Latency**: Negligible ($O(N_{\text{swarms}})$, $< 0.02\text{ ms/tick}$).
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Add `zoochory_seed_payload` field to `SwarmComponent`, isolate PRNG seed generator per swarm entity, and update `interaction.py` for seed transport along velocity vectors ($\sim 180$ LOC).
  * **UI & Dashboard**: Add "Zoochory Vector Settings" form inputs to herbivore species modal editor; update scenario JSON export/import buttons.
  * **Empirical Bio-Database Pipeline**: Update `src/data_pipeline/archetype_extractor.py` to map seed gut-retention times from PanTHERIA / GloBI datasets into `bio_database.json`.
  * **Telemetry & Replay Schema**: Direct update to Zarr swarm entity metadata attributes.
  * **QA & Verification Gates**: Integration tests verifying deterministic zoochory transport under identical PRNG seeds.
  * **Documentation**: Update `docs/scientific_model/ecological_analytics.md` with zoochory dispersal kernel formulations.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#2-sub-stage-22-zoochory-dispersal) for new continuous/discrete genes (`gut_retention_ticks`, `zoochory_vector_species_mask`).

---

### Sub-Stage 2.3: Trait-Based Herbivore Demographic State Machines (v2.3)

* **Biological Target**: Generalize insect development from static swarms into data-driven ECS developmental morphs (sessile incubation $\to$ localized grazing larvae $\to$ adult macro-dispersal flight) driven by degree-days and nutritional intake.
* **Standalone Researcher Utility**: Enables entomologists and agricultural researchers to simulate multi-instar pest outbreaks, egg-laying preferences, and stage-specific grazing damage without needing soil or weather systems.
* **Computational & Performance Cost**:
  * **Memory**: $+64\text{ Bytes/entity}$ for development tracking components.
  * **CPU Latency**: $< 0.08\text{ ms/tick}$ via vectorized ECS entity processing.
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Create `DevelopmentComponent` and `MobilityComponent` in `phids.engine.components`, and add developmental state machine transitions in `interaction.py` ($\sim 400$ LOC).
  * **UI & Dashboard**: Add multi-stage lifecycle tabs in the Herbivore Species UI editor; enable per-stage population telemetry charts on the live HTMX dashboard.
  * **Empirical Bio-Database Pipeline**: Add instar metabolic rates and incubation degree-days to `HerbivoreSpeciesParams` ETL schemas in `src/data_pipeline/transform.py`.
  * **Telemetry & Replay Schema**: Direct update to Zarr tick metrics to track instar stage distributions.
  * **QA & Verification Gates**: State machine invariant tests ensuring conservation of population across metamorphosis steps.
  * **Documentation**: Create dedicated lifecycle kinetics guide in `docs/scientific_model/`.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#3-sub-stage-23-trait-based-herbivore-demographic-state-machines) for new instar transition genes.

---

### Sub-Stage 2.4: Soil Detritus & Biomass Recycling Loop (v2.4)

* **Biological Target**: Convert dead plant tissue and herbivore carcasses into an organic detritus layer ($B_{\text{detritus}}$) that mineralizes into bio-available soil nitrogen ($N_{\text{soil}}$), establishing a closed-loop nutrient cycle.
* **Standalone Researcher Utility**: Provides soil scientists and ecosystem ecologists with a tool to investigate nutrient turnover, plant competition under nitrogen limitation, and organic fertilizing feedback loops.
* **Computational & Performance Cost**:
  * **Memory**: Dense Mode: $+8\text{ Bytes/cell}$ ($\sim 2\text{ MB}$ for $512^2$). Macro-Patch Mode ($16 \times 16$ coarse grid): $+32\text{ Bytes/patch}$ ($\sim 32\text{ KB}$).
  * **CPU Latency**: Dense Mode: $\sim 0.10\text{ ms/tick}$. Macro-Patch Mode: $< 0.01\text{ ms/tick}$.
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Add `SoilModule` to `GridEnvironment`, implement JIT mineralization kernels, and hook dead entity biomass into detritus pools during `lifecycle.py` and `interaction.py` passes ($\sim 350$ LOC).
  * **UI & Dashboard**: Add "Soil & Biomass Recycling" settings panel (mode selection: Disabled / Dense / Macro-Patch 16x16), initial nitrogen slider, scenario JSON export/import bindings, and a live 2D "Soil Nitrogen Overlay" map view.
  * **Empirical Bio-Database Pipeline**: Update DuckDB tables with soil nitrogen baselines and plant tissue N:P decomposition ratios.
  * **Telemetry & Replay Schema**: Direct update to Zarr schema adding `/soil_nitrogen` matrix layer when enabled.
  * **QA & Verification Gates**: Nitrogen and total biomass conservation law integration tests.
  * **Documentation**: Update `docs/technical_architecture/system_architecture.md` with soil double-buffering layers.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#4-sub-stage-24-soil-detritus--biomass-recycling) for soil mineralization continuous/discrete genes.

---

### Sub-Stage 2.5: Macro-Patch Weather & Micro-Climate Profile (v2.5)

* **Biological Target**: Introduce dynamic seasonal/diurnal temperature $T(t)$, relative humidity $H(t)$, and rainfall pulses $W(t)$ that modulate photosynthesis rates, VOC diffusion constants ($D_{\text{VOC}}(T)$), and insect activity.
* **Standalone Researcher Utility**: Enables climate change impact assessments, heatwave/drought stress experiments, and diurnal VOC emission studies.
* **Computational & Performance Cost**:
  * **Memory**: $< 1\text{ KB}$ (scalar or $K \times K$ macro-patch struct).
  * **CPU Latency**: $< 0.03\text{ ms/tick}$.
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Implement `WeatherModule` in `phids.engine.core` and integrate climate parameter updates into `SimulationLoop.step()` Phase 0 ($\sim 220$ LOC).
  * **UI & Dashboard**: Add "Weather Profile" selection menu (Constant, Sinusoidal Seasonal, Drought Pulse), ambient temperature live telemetry badge on the top dashboard bar, and scenario JSON import/export support.
  * **Empirical Bio-Database Pipeline**: Ingest species thermal tolerance limits ($T_{\text{min}}, T_{\text{max}}$) into `bio_database.json`.
  * **Telemetry & Replay Schema**: Record global climate scalars directly in Zarr frame metadata.
  * **QA & Verification Gates**: Validate Arrhenius reaction rate scaling tests for VOC synthesis.
  * **Documentation**: Update `docs/scientific_model/mathematical_framework.md` with temperature-dependent Arrhenius kinetics for VOC synthesis.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#5-sub-stage-25-macro-patch-weather-profiles) for climate amplitude and drought intensity genes.

---

### Sub-Stage 2.6: 3D Vertical Canopy Structure & Boundary Layer Diffusion (v2.6)

* **Biological Target**: Extend atmospheric VOC diffusion to 3D vertical grid layers ($W \times H \times Z$), modeling height-dependent wind shear, canopy boundary layer resistance, and vertical thermal convection.
* **Standalone Researcher Utility**: Provides atmospheric chemists and forest canopy ecologists with 3D VOC plume visualization and vertical thermal stratification analysis.
* **Computational & Performance Cost**:
  * **Memory**: $+4 \times Z\text{ Bytes/cell}$ ($\sim 8\text{ MB}$ for $Z=8, 512^2$).
  * **CPU Latency**: $\sim 1.20\text{ ms/tick}$ (parallelized 3D Numba JIT kernel).
* **Implementation Effort & Full-Stack Scope**:
  * **Backend & API**: Expand 2D `GridEnvironment` signaling arrays to 3D NumPy arrays ($W \times H \times Z$) and implement 3D Numba stencil solvers in `signaling.py` ($\sim 650$ LOC).
  * **UI & Dashboard**: Add 3D layer height selector slider, vertical profile slice charts in HTMX UI, and scenario JSON import/export bindings for $Z$-layer configurations.
  * **Empirical Bio-Database Pipeline**: Map canopy height classes and boundary layer resistance coefficients in `src/data_pipeline/`.
  * **Telemetry & Replay Schema**: Upgrade Zarr signal datasets directly to 3D tensor arrays ($T \times W \times H \times Z$). Example scenarios updated to 3D formats.
  * **QA & Verification Gates**: 3D conservation of mass tests and Numba SIMD vectorization benchmarks.
  * **Packaging**: Re-verify PyInstaller standalone binary performance on Linux/macOS/Windows.
  * **Documentation**: Update `docs/technical_architecture/engine_execution.md` with 3D stencil array memory layouts.
  * **DSE Scope Extension**: Cross-reference [Design Space Exploration Guide](file:///home/benni/Documents/antigravity_workspace/PHIDS/docs/scenario_guide/design_space_exploration.md#6-sub-stage-26-3d-canopy-structure) for vertical canopy height $Z$ and shear alpha parameters.

---

## Phase 3: Distributed HPC Execution & AI-Driven Ecosystem Optimization (v3.0 - Future Vision)

### Sub-Stage 3.1: GPU-Accelerated PyTorch/CUDA PDE Engines (v3.1)

* **Computational Target**: Port 2D/3D reaction-diffusion cellular automata layers to GPU tensor accelerators (PyTorch / CUDA C++ kernels).
* **Standalone Researcher Utility**: Enables real-time simulation of massive biotope grids ($2048 \times 2048$ to $4096 \times 4096$) at over 60 FPS.
* **Implementation Effort & Scope**: High ($\sim 800$ LOC; CUDA kernel bindings). Offloads CPU memory; GPU execution time $< 0.20\text{ ms/tick}$.

---

### Sub-Stage 3.2: AI Agent Design Space Exploration (DSE) & Coevolution (v3.2)

* **Computational Target**: Automate Pareto multi-objective optimization using reinforcement learning and genetic algorithms to discover optimal plant defense investment strategies under multi-stress climate scenarios.
* **Standalone Researcher Utility**: Provides evolutionary biologists with automated discovery of non-dominated evolutionary stable strategies (ESS) for plant chemical and morphological defense.
* **Implementation Effort & Scope**: High ($\sim 700$ LOC; Ray/Tune distributed integration). Cluster-scale parallel execution ($O(N_{\text{simulations}})$).

---

## Phase 2 Implementation Summary Matrix

| Sub-Stage | Core Feature | Dev Complexity | Backend & API | UI & Scenario Import/Export | Empirical DB & ETL | Zarr Telemetry & QA Gates | Target Docs | DSE Parameters Added |
|---|---|---|---|---|---|---|---|---|
| **v2.1** | Soil Seed Bank | Low-Mod ($\sim 250$ LOC) | `seed_bank_layer`, `lifecycle.py` GDD logic | HTMX Seed Bank toggle, GDD sliders, JSON buttons, live overlay | Ingest `gdd_threshold`, `seed_decay` in DuckDB | Direct `/seed_bank_density` Zarr update, `mutmut` $>85\%$ | `engine_execution.md` | `germination_gdd_threshold`, `seed_decay_rate` |
| **v2.2** | Zoochory Dispersal | Low ($\sim 180$ LOC) | `SwarmComponent` payload, `interaction.py` | Zoochory vector settings modal, scenario JSON export/import | Map gut retention times from PanTHERIA/GloBI | Deterministic PRNG seed transport tests | `ecological_analytics.md` | `gut_retention_ticks`, `zoochory_vector_mask` |
| **v2.3** | Trait Herbivore Morphs | Moderate ($\sim 400$ LOC) | `DevelopmentComponent`, instar transitions | Multi-stage species UI editor, per-stage telemetry charts | Instar metabolic & incubation ETL in `transform.py` | Instar population telemetry in Zarr | New lifecycle kinetics doc | Instar transition degree-days & upkeep |
| **v2.4** | Soil Detritus Recycling | Moderate ($\sim 350$ LOC) | `SoilModule` JIT mineralization kernels | Soil settings panel (Disabled/Dense/Patch), live N-map | Soil N baselines & tissue N:P decay ratios | Direct `/soil_nitrogen` Zarr array | `system_architecture.md` | `mineralization_rate`, `soil_nitrogen_baseline` |
| **v2.5** | Weather Profiles | Low-Mod ($\sim 220$ LOC) | `WeatherModule`, `SimulationLoop` Phase 0 | Weather profile selector, dashboard temp badge | Species thermal limits ($T_{\text{min}}, T_{\text{max}}$) in JSON | Direct climate scalars in Zarr metadata | `mathematical_framework.md` | `seasonal_temp_amplitude`, `drought_factor` |
| **v2.6** | 3D Canopy VOCs | High ($\sim 650$ LOC) | 3D arrays ($W\times H\times Z$), 3D Numba stencils | 3D layer height slider, vertical slice charts | Canopy height & boundary resistance ETL | Direct 3D tensor Zarr datasets | `engine_execution.md` | `canopy_height_layers`, `wind_shear_alpha` |
