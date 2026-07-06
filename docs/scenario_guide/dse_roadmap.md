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

* **The Invariant:** The maximum possible caloric intake of a herbivore swarm in a single tick must be mathematically greater than its base metabolic upkeep.
* **Correction Logic:** If Plant A's $E_{max}$ is locked to $10.0$ and Herbivore B's $Metabolism$ is locked to $15.0$, the system throws a warning: *"Herbivore B will mathematically starve. Feasible adjustment: Unlock Plant A's Max Energy, or reduce Herbivore B's Upkeep below 10.0."*

### 1.2 Dietary and Trophic Coherence

Ecosystems must be fully connected graphs.

* **The Invariant:** Every herbivore species present in the simulation *must* be capable of eating at least one plant species. Conversely, every plant species present *must* be preyed upon by at least one herbivore species (to prevent unchecked, infinite growth).
* **Correction Logic:** If a user configures 3 plants and 1 herbivore, but restricts the herbivore's diet matrix to only 2 of the plants, the parser will flag the 3rd plant as an invalid, non-interacting entity.

### 1.3 Chemical Mechanism Integrity (Signals & Toxins)

The biochemical defense network cannot contain "dead ends" or unused mechanisms.

* **Signal Continuity:** A signal (airborne or mycorrhizal) is only valid if it triggers a tangible outcome. If Signal A triggers Signal B, Signal B *must* eventually trigger an active defense (e.g., a lethal or repellent Toxin). A signal that triggers nothing is invalid and pruned.
* **Herbivore Triggers:** A signal or defense mechanism is only instantiated if it is explicitly mapped to an attacking herbivore. Plants do not synthesize toxins in a vacuum.
* **Receptivity:** Toxins and repellents are only valid if there is at least one herbivore species in the simulation susceptible to them.

---

## 2. The Configuration UI (Tabbed Layout)

To provide an intuitive Human-In-The-Loop (HITL) experience, the Fast API/HTMX webview organizes the DSE configuration into modular, tabbed views nested at the bottom of the Biotope configuration menu.

### Tab 1: The Canvas & Spatial Density

This tab defines the invariant physical arena and the mathematical goals. Parameters not explicitly locked here are left for the DSE to manipulate.

* **Grid Dimensions (Mandatory):** `Width` and `Height` of the biotope.
* **Stability Targets (Mandatory):**
  * *Target Ticks:* Minimum duration the ecosystem must survive to be considered a stable equilibrium (e.g., 5000 ticks).
  * *Batch Replicates:* Number of parallel seeds run per genotype to prove the equilibrium is mathematically robust (e.g., 5).
  * *Success Threshold:* The percentage of replicates that must hit the Target Ticks (e.g., 80%).

* **Spatial Distribution & Density Bounds:**
  * *Placement Strategy:* Random Uniform, Clustered, or Banded.
  * *Flora Density:* Adjustable individually per species (e.g., $5\%$ to $15\%$ initial grid coverage). *Feasibility Check:* The sum of all plant densities cannot exceed $100\%$ of the grid size, as plants occupy exactly one coordinate each.
  * *Herbivore Swarm Density:* Number of starting swarms. Swarms *can* occupy overlapping fields, so their density is not strictly bound by absolute grid tile count, but is checked against starting plant caloric capacity.

### Tab 2: Complexity & The Evolutionary Toolkit

This defines the structural complexity (the Integer/Boolean genes of the MINLP) the DSE is permitted to invent or mutate.

* **Species Counts (Mandatory):**
  * Number of distinct Plant species (up to 16).
  * Number of distinct Herbivore swarms (up to 16).

* **Mechanism Toggles:** Checkboxes defining the available toolkit:
  * `[ ]` Allow Toxins (Lethal/Repellent).
  * `[ ]` Allow Airborne Signals.
  * `[ ]` Allow Multi-Level Signals (Cascades).
  * `[ ]` Allow Mycorrhizal (Root) Networks & Inter-species sharing.
  * *Note:* If the user requests specific DB Archetypes that inherently rely on these traits, the UI auto-checks these boxes.

### Tab 3: Search Modes (The "Wiggle Room")

Here, the user defines the parameter search space and the database connection strategy.

#### Mode A: Generative (Tabula Rasa)

The DSE has mathematical freedom to generate species parameters, bounds, and matrices to fulfill the Lotka-Volterra equilibrium.

* **Database Constraints Checkbox:**
  * `[x] Strict Database Resemblance:` The DSE is only allowed to generate parameters that resemble known individuals (plants/herbivores/toxins) from the database within a defined biological tolerance range.
  * `[ ] Allow Novel Generation:` The DSE can freely invent entirely new parameters and interaction topologies, creating hypothetical placeholder species.

* **Post-Processing:** Once an equilibrium is found, the system uses K-Nearest Neighbors (KNN) or Cosine Similarity against `bio_database.json` to assign real-world names to the dynamically generated entities that closest match their traits.

#### Mode B: Constrained (Archetype Anchoring)

The user pre-selects exact biological profiles, forcing the DSE to navigate around established configurations.

* **Slot-Based Configuration:** The UI renders a slot for every requested plant and herbivore (e.g., Plant 1, Plant 2, Herbivore 1).
* **Archetype Selection:** Users choose specific species (e.g., *Taxus baccata*) equipped with predefined trigger rules, diet matrices, and substances.
* **The "Wiggle Room":** The DSE is tightly constrained. It may only mutate the parameters of chosen representatives within a strict $\pm 20\%$ variance bound to achieve equilibrium.
* **Mixed Ecosystems:** The user may select DB archetypes for *some* slots while leaving the remaining required slots as "Novel/Dynamically Generated." The DSE will hold the archetypes relatively fixed while wildly mutating the novel slots to bridge the ecological gaps.

---

## 4. The Live Execution Flow (Human-in-the-Loop)

1. **Validation:** The user clicks "Validate". The Backend parser ensures no thermodynamic or structural rules are violated.
2. **Execution:** The user clicks "Run Equilibrium Finder". The request is sent to the backend, which spins up a decoupled background `asyncio` task to prevent blocking the main FastAPI thread.
3. **Telemetry Stream:** The UI swaps to a live WebSocket view, rendering a real-time scatterplot and a "Top Candidates" grid showing generations, longevity scores, and Coefficient of Variation (CV) stability.
4. **Application:** The user selects a successful ecosystem from the grid and clicks **"Apply to Draft"**. The DSE automatically stops, and the winning structural and continuous parameters are injected into the active `DraftState`, ready for visual simulation.

---

## 5. Modular Software Architecture

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
