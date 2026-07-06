---
type: concept
title: "Design Space Exploration (DSE): The Equilibrium Finder"
status: active
version: 3.0
description: "Comprehensive architecture, UI/UX flow, and strict logical invariants for the PHIDS Evolutionary DSE."
---

# Design Space Exploration (DSE): The Equilibrium Finder

The Plant-Herbivore Interaction & Defense Simulator (PHIDS) utilizes an **Evolutionary Encapsulated Multi-Stage Design Space Exploration (DSE)** framework. The DSE is not a generic "number maximizer"; it is a highly specialized scientific instrument designed to discover **stable Lotka-Volterra model equilibria**. It systematically searches a vast Mixed-Integer Non-Linear Programming (MINLP) landscape of ecological parameters, spatial configurations, and interaction topologies to find balanced, cyclical ecosystem survival without causing mass extinction or runaway growth.

Because discovering a true multi-species equilibrium is computationally intensive, the DSE requires a meticulously configured initial state (the "Canvas") and a rigorous, real-time validation parser to prevent the optimization loop from attempting to solve mathematically impossible scenarios.

---

## 1. The Pre-Flight Gatekeeper: Logical & Biological Invariants

Before the DSE can spin up a background worker thread, the configuration must pass through a strict, real-time logical parser. Every adjustment made in the UI immediately triggers a system-wide revalidation. If an impossible constraint combination is detected, the UI locks the execution and provides an actionable, feasible adjustment to the user.

### 1.1 The Thermodynamic Chain

Organisms are bound by strict caloric mathematics. If the user explicitly locks certain biological parameters, the parser evaluates the chain:

*   **The Invariant:** The maximum possible caloric intake of a herbivore swarm in a single tick must be mathematically greater than its base metabolic upkeep.
*   **Correction Logic:** If Plant A's $E_{max}$ is locked to $10.0$ and Herbivore B's $Metabolism$ is locked to $15.0$, the system throws a warning: *"Herbivore B will mathematically starve. Feasible adjustment: Unlock Plant A's Max Energy, or reduce Herbivore B's Upkeep below 10.0."*

### 1.2 Dietary and Trophic Coherence

Ecosystems must be fully connected graphs.

*   **The Invariant:** Every herbivore species present in the simulation *must* be capable of eating at least one plant species. Conversely, every plant species present *must* be preyed upon by at least one herbivore species (to prevent unchecked, infinite growth).
*   **Correction Logic:** If a user configures 3 plants and 1 herbivore, but restricts the herbivore's diet matrix to only 2 of the plants, the parser will flag the 3rd plant as an invalid, non-interacting entity.

### 1.3 Chemical Mechanism Integrity (Signals & Toxins)

The biochemical defense network cannot contain "dead ends" or non-functional pathways.

*   **Signal Functional Continuity:** A signal (airborne or mycorrhizal) is only valid if it triggers a tangible outcome. If Signal A triggers Signal B, Signal B *must* eventually trigger a defense mechanism (e.g., a lethal or repellent Toxin). A signal that triggers nothing is invalid.
*   **Herbivore Susceptibility Alignment:** A defense mechanism (like a repellent or toxin) is only valid if there is at least one herbivore species in the simulation susceptible to it. For example, generating a repellent that targets a non-existent herbivore species represents a thermodynamic waste and is rejected by the pre-flight gatekeeper.
*   **Trigger Sanity:** Toxins and signals must have a valid trigger condition that can actually occur in the simulation (e.g., triggered by a herbivore species that is present and eats the plant, or by an environmental signal that can actually be emitted by a neighbor).

### 1.4 Spatial Density and Placement Invariants

Plants and herbivores have distinct spatial restrictions that must be validated relative to the biotope size:

*   **Field Size Constraint:** Choosing the grid dimensions (Width and Height) is mandatory.
*   **Plant Density Cap:** Each plant individual occupies exactly one coordinate. The sum of all initial plant coverages (expressed as a density percentage) cannot exceed $100\%$ of the total grid area.
*   **Swarm Overlap Tolerance:** Herbivore swarms *can* overlap and occupy the same coordinates. Swarm placement density is not capped at $100\%$, but is checked against the total initial plant caloric capacity to prevent instant starvation on tick 1.

### 1.5 Chaining and Feasible Corrections

All relative parameters are logically chained in the pre-flight validator. If any thermodynamic, dietary, chemical, or spatial constraint is violated, the validation engine returns a detailed, user-friendly correction message detailing the specific parameters to adjust.

---

## 2. The Configuration UI (Tabbed Layout)

To provide an intuitive Human-In-The-Loop (HITL) experience, the FastAPI/HTMX webview organizes the DSE configuration into modular, tabbed views nested at the bottom of the Biotope configuration menu.

### Tab 1: The Canvas & Spatial Setup

This tab defines the physical arena, placement rules, and validation targets.

*   **Grid Dimensions (Mandatory):** Width and Height of the biotope.
*   **Biotope Configuration:** Specific outcome-affecting parameters (e.g., initial environmental signals, default decay rates) can be configured. Parameters left unselected are automatically chosen or optimized by the DSE. (Simulation runtime/performance options like speed in Hz are excluded from optimization).
*   **Spatial Distribution & Density:**
    *   *Placement Strategy:* Random Uniform, Clustered, or Banded.
    *   *Random Distribution Toggle:* Checkbox to randomize coordinates upon initialization.
    *   *Flora Density:* Configurable coverage percentage per plant species, bounded by total tile count.
    *   *Swarm Density:* Configurable swarm count, allowing multi-swarm overlap.
*   **Stability Targets (Mandatory):**
    *   *Target Ticks:* Minimum duration the ecosystem must survive to be considered stable (e.g., 5000 ticks).
    *   *Batch Replicates (Validation Batch Size):* Number of parallel seeds run per genotype to prove mathematical robustness (e.g., 5 replicates).
    *   *Success Threshold:* The percentage of replicates in the batch that must reach the Target Ticks (e.g., 80%).

### Tab 2: Complexity & The Biochemical Toolkit

This defines the structural complexity (the Integer/Boolean genes of the MINLP) the DSE is permitted to manipulate.

*   **Species Counts:**
    *   Number of distinct Plant species (up to 16).
    *   Number of distinct Herbivore swarms (up to 16).
*   **Biochemical Mechanism Configurator:**
    *   *Substance Counts:* Number of active toxins and signals.
    *   *Multi-Level Signals Toggle:* Checkbox to allow recursive signaling cascades.
    *   *Mycorrhiza Toggle:* Checkbox to allow root-network signaling.
    *   *Inter-Species Mycorrhiza Toggle:* Checkbox to allow mycorrhizal connections between different plant species.
    *   *Note:* The assignment of these substances (which plant uses what signal or toxin) depends on database records, diet matrices, and triggering/effect relationships.

### Tab 3: Exploration & Database Matching

Here, the user defines the parameter search space bounds and how closely the DSE must stick to real-world biology.

*   **Database Constraints Toggle:**
    *   `[x] Strict Database Resemblance:` The DSE is only allowed to generate parameters that resemble known individuals (plants/herbivores/toxins) from the database within a defined tolerance range (e.g., $\pm 20\%$).
    *   `[ ] Allow Novel Generation:` The DSE can freely invent entirely new parameters and interaction topologies, creating hypothetical placeholder species.
*   **Exploration Mode selection:**
    *   **Mode A: Generative (Tabula Rasa):** The DSE has mathematical freedom to generate species parameters, bounds, and matrices from scratch to satisfy the stability targets. Post-run, KNN matching is used to name generated placeholder species with their closest real-world equivalents.
    *   **Mode B: Constrained (Archetype Anchoring):** 
        *   The user pre-selects specific species archetypes (e.g., *Taxus baccata*) from the database for a subset of slots, carrying over their real diet matrices, trigger rules, and substances.
        *   The remaining slots (Total Species Count minus pre-selected slots) are left to be filled by the DSE's evolutionary solver.
        *   User-configured archetype parameters can either be locked completely or set to mutate within a tight variance limit (e.g., $\pm 20\%$).

---

## 3. The Live Execution Flow (Human-in-the-Loop)

1.  **Validation:** The user clicks "Validate". The Backend parser ensures no thermodynamic, spatial, or structural rules are violated.
2.  **Execution:** The user clicks "Run DSE". The request is sent to the backend, which spins up a decoupled background `asyncio` task to prevent blocking the main FastAPI thread.
3.  **Telemetry Stream:** The UI swaps to a live WebSocket view, rendering a real-time scatterplot and a "Top Candidates" grid showing generations, longevity scores, and Coefficient of Variation (CV) stability.
4.  **Application:** The user selects a successful ecosystem from the grid and clicks **"Apply to Draft"**. The DSE automatically stops, and the winning structural and continuous parameters are injected into the active `DraftState`, ready for visual simulation.

---

## 4. Modular Software Architecture

To prevent unmaintainable "god-modules" and ensure strict HTMX swapping logic, the codebase adheres to a rigid, decoupled directory structure.

### Frontend (Jinja/HTMX Partials)

```text
src/phids/api/templates/dse/
├── container.html              # The main tab wrapper nested under Biotope Config
├── tabs/
│   ├── canvas_targets.html     # Tab 1: Grid, Density, Replication rules
│   ├── complexity_toolkit.html # Tab 2: Species counts, Signals, Mycorrhiza
│   └── exploration_modes.html  # Tab 3: Mode A/B toggles, DB Archetype Slots
└── components/
    ├── archetype_slot.html     # Reusable DB dropdown component
    ├── preflight_alert.html    # The real-time parser warning box
    └── live_pareto.html        # WebSocket listener & Candidate Selection grid
```

### Backend (FastAPI Services & Parsers)

```text
src/phids/api/routers/dse/
├── __init__.py
├── orchestrator.py             # POST /start and POST /stop
├── validation.py               # POST /validate (Triggers the Invariant Parser)
└── apply.py                    # POST /apply (Merges selected phenotype to DraftState)

src/phids/api/services/dse/
├── __init__.py
├── task_manager.py             # Manages async.to_thread and threading.Event cancellation
├── invariant_parser.py         # Executes the Thermodynamic and Chemical Chain logic
├── bounds_builder.py           # Translates UI State -> DEAP min/max search tuples
└── db_matcher.py               # Evaluates Mode A/B KNN database logic and ±20% clamping
```
