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

## Current Achieved UI State & Preparations

As of the current iteration, significant milestones have been achieved in decoupling the underlying biological schema and building the UI foundations required for the DSE:

* **Standalone Database UI:** The configuration interface no longer relies on manual JSON writing. It dynamically reads and writes biological templates through an interactive frontend dashboard.
* **Graphical Trigger Builder:** Complex logic (like checking `Substance Active` or `Herbivore Presence` conditions) is now managed via graphical forms using implicit `ALL_OF` structures, ensuring syntax-perfect engine configurations.
* **Trophic and Chemical Unification:** Herbivore diet matrices and Flora substance defenses are explicitly cross-referenced. Substances now exist as standalone entities in the master database rather than localized properties, allowing the DSE optimizer to freely swap and mutate toxins/signals independently from the host plants.
* **Headless UI Validation:** To ensure rock-solid stability during rapid HTMX interaction and JSON parsing, a highly aggressive headless test suite validates DOM integrity and strictly checks Javascript bindings via background `node -c` subprocesses.

---

## 1. The Pre-Flight Gatekeeper: Logical & Biological Invariants

Before the DSE can spin up a background worker thread, the configuration must pass through a strict, real-time logical parser. Every adjustment made in the UI immediately triggers a system-wide revalidation. If an impossible constraint combination is detected, the UI locks the execution and provides an actionable, feasible adjustment to the user.

### 1.1 The Thermodynamic Chain

Organisms are bound by strict caloric mathematics. If the user explicitly locks certain biological parameters, the parser evaluates the chain:

* **The Invariant:** The maximum possible caloric intake of a herbivore swarm in a single tick must be mathematically greater than its base metabolic upkeep.
* **Correction Logic:** If Plant A's $E_{max}$ is locked to $10.0$ and Herbivore B's $Metabolism$ is locked to $15.0$, the system throws a warning: *"Herbivore B will mathematically starve. Feasible adjustment: Unlock Plant A's Max Energy, or reduce Herbivore B's Upkeep below 10.0."*

### 1.2 Dietary and Trophic Coherence

Ecosystems must be fully connected graphs.

* **The Invariant:** Every herbivore species present in the simulation *must* be capable of eating at least one plant species. Conversely, every plant species present *must* be preyed upon by at least one herbivore species (to prevent unchecked, infinite growth).
* **Correction Logic:** If a user configures 3 plants and 1 herbivore, but restricts the herbivore's diet matrix to only 2 of the plants, the parser will flag the 3rd plant as an invalid, non-interacting entity.

### 1.3 Chemical Mechanism Integrity (Signals & Toxins)

The substance defense network cannot contain "dead ends" or non-functional pathways.

* **Signal Functional Continuity:** A signal (airborne or mycorrhizal) is only valid if it triggers a tangible outcome. If Signal A triggers Signal B, Signal B *must* eventually trigger a defense mechanism (e.g., a lethal or repellent Toxin). A signal that triggers nothing is invalid.
* **Herbivore Susceptibility Alignment:** A defense mechanism (like a repellent or toxin) is only valid if there is at least one herbivore species in the simulation susceptible to it. For example, generating a repellent that targets a non-existent herbivore species represents a thermodynamic waste and is rejected by the pre-flight gatekeeper.
* **Trigger Sanity:** Toxins and signals must have a valid trigger condition that can actually occur in the simulation (e.g., triggered by a herbivore species that is present and eats the plant, or by an environmental signal that can actually be emitted by a neighbor).

### 1.4 Spatial Density and Placement Invariants

Plants and herbivores have distinct spatial restrictions that must be validated relative to the biotope size:

* **Field Size Constraint:** Choosing the grid dimensions (Width and Height) is mandatory.
* **Plant Density Cap:** Each plant individual occupies exactly one coordinate. The sum of all initial plant coverages (expressed as a density percentage) cannot exceed $100\%$ of the total grid area.
* **Swarm Overlap Tolerance:** Herbivore swarms *can* overlap and occupy the same coordinates. Swarm placement density is not capped at $100\%$, but is checked against the total initial plant caloric capacity to prevent instant starvation on tick 1.

### 1.5 Chaining and Feasible Corrections

All relative parameters are logically chained in the pre-flight validator. If any thermodynamic, dietary, chemical, or spatial constraint is violated, the validation engine returns a detailed, user-friendly correction message detailing the specific parameters to adjust.

---

## 2. The Configuration UI (Unified Layout)

To provide an intuitive Human-In-The-Loop (HITL) experience, the FastAPI/HTMX webview organizes the DSE configuration into a streamlined, single-page layout.

### Operation Modes & Exploration

The user defines the parameter search space bounds and how closely the DSE must stick to real-world biology.

* **Mode A: Generative (Tabula Rasa):** The DSE has mathematical freedom to generate species parameters, bounds, and matrices from scratch to satisfy the stability targets. Post-run, KNN matching is used to name generated placeholder species with their closest real-world equivalents.
* **Mode B: Constrained (Archetype Anchoring):**
  * The user explicitly defines the exact number of **Total Flora Species** and **Total Herbivore Swarms**.
  * An **Ecosystem Composition** builder dynamically creates a dropdown slot for each flora/herbivore.
  * For each individual slot, the user can either select a specific database archetype (e.g., *Taxus baccata*) or leave it as `[DSE Invents]`.
  * The optimizer anchors its search space bounds to &plusmn;20% for any specified archetypes, and optimizes freely for the `[DSE Invents]` slots.

### Advanced Configuration (Variable vs. Constant)

Beneath the Operation Modes, users can expand an **Advanced Configuration** accordion to impose strict bounds on the optimization process. Every parameter features a **Lock Toggle (🔓/🔒)** allowing the user to decide if the value should be dynamically optimized by the DSE (Variable) or strictly enforced (Constant).

* **Canvas & Stability Targets:**
  * *Target Ticks (Variable/Constant):* Duration the ecosystem must survive.
  * *Validation Batch Size (Strict Constant):* Number of replicates run per genotype.
  * *Success Threshold (Strict Constant):* Required survival rate across the batch (e.g., 80%).
* **Complexity Limits:**
  * *Max Flora Species (Variable/Constant)*
  * *Max Herbivore Swarms (Variable/Constant)*
  * *Max Toxins/Signals (Variable/Constant)*
* **Spatial Distribution:**
  * *Placement Strategy (Variable/Constant):* Uniform, Clustered, or Banded.
  * *Max Grid Density % (Variable/Constant)*

---

## 3. The Live Execution Flow (Human-in-the-Loop)

1. **Validation:** The user clicks "Validate". The Backend parser ensures no thermodynamic, spatial, or structural rules are violated.
2. **Execution:** The user clicks "Run DSE". The request is sent to the backend, which spins up a decoupled background `asyncio` task to prevent blocking the main FastAPI thread.
3. **Telemetry Stream:** The UI swaps to a live WebSocket view, rendering a real-time scatterplot and a "Top Candidates" grid showing generations, longevity scores, and Coefficient of Variation (CV) stability.
4. **Application:** The user selects a successful ecosystem from the grid and clicks **"Apply to Draft"**. The DSE automatically stops, and the winning structural and continuous parameters are injected into the active `DraftState`, ready for visual simulation.

---

## 4. Modular Software Architecture

To prevent unmaintainable "god-modules" and ensure strict HTMX swapping logic, the codebase adheres to a rigid, decoupled directory structure.

### Frontend (Jinja/HTMX Partials)

```text
src/phids/api/templates/dse/
├── container.html              # The main 2-column layout for modes and live eval
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
