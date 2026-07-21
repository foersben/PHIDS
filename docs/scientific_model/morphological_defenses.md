---
type: concept
title: Morphological Defenses and Senescence
status: active
version: 1.0
description: Architectural record for morphological defenses and dynamic resource
  reallocation.
tags:
- phids
- ecs
- numba
- performance
- python
timestamp: "2026-07-21T16:01:38Z"
resources:
- src/phids/api/schemas.py
- src/phids/engine/components/plant.py
- swarm.py
- signaling.py
- src/phids/engine/core/flow_field.py
- src/phids/engine/systems/interaction.py
---

This document outlines the architectural implementation for the biological accuracy of the PHIDS engine, specifically the separation of morphological (passive) defenses from active chemical defenses, and dynamic resource reallocation (apparent nutrition withdrawal).

---

## Step-by-Step Implementation Details

### Step 1: Pydantic Schemas & Data Contracts

**Target File:** `src/phids/api/schemas.py`

1. **Introduce `PassiveDefensesSchema`**:

    ```python
    class PassiveDefensesSchema(StrictBaseModel):
        """Morphological (passive) defenses of a flora species."""
        mechanical_damage_per_bite: float = Field(default=0.0, ge=0.0, description="Thorns/spines damage per feeding event.")
        digestibility_modifier: float = Field(default=1.0, ge=0.0, le=1.0, description="Lignin/silica calorie discount multiplier (e.g. 0.5 = 50% metabolized).")
    ```

2. **Add `passive_defenses` to `FloraSpeciesParams`**:

    ```python
    passive_defenses: PassiveDefensesSchema = Field(default_factory=PassiveDefensesSchema)
    ```

3. **Add `resistances` to `HerbivoreSpeciesParams`**:

    ```python
    resistances: dict[str, float] = Field(default_factory=dict, description="Resistances to defense mechanisms (e.g. {'mechanical': 0.5}).")
    ```

4. **Update `TriggerActionSchema`**:
    * Refactor the trigger action model to represent a discriminated union of action types using Pydantic's `Field(discriminator="type")`.
    * **Action A**: `synthesize_substance` (holds the existing substance parameters: `substance_id`, `synthesis_duration`, etc.).
    * **Action B**: `resource_withdrawal` (holds `apparent_nutrition_factor: float = 1.0` and duration parameters).

---

### Step 2: ECS Component Expansion

**Target Files:** `src/phids/engine/components/plant.py` and `swarm.py`

1. In `PlantComponent`, add `apparent_nutrition_factor: float = 1.0` as a mutable runtime float scalar. This tracks the apparent attraction level of the plant.
2. Ensure that the signaling lifecycle tracker (e.g., in `signaling.py`) manages resetting this value back to 1.0 when a `resource_withdrawal` trigger action duration expires.

---

### Step 3: Numba Flow-Field Manipulation

**Target File:** `src/phids/engine/core/flow_field.py`

1. Locate the JIT-accelerated kernel `_compute_flow_field_impl` which takes plant energy and toxin levels.
2. Pass a 2D array of `apparent_nutrition_factors` matching the grid layout.
3. During baseline calculation:

    ```python
    base[x, y] = (plant_energy[x, y] * apparent_nutrition_factor[x, y]) - toxin_sum[x, y]
    ```

    This scales the attractant signal of the plant dynamically before it is diffused across the grid.

---

### Step 4: The Trophic Interaction Loop (Feeding)

**Target File:** `src/phids/engine/systems/interaction.py`

1. In the `_process_feeding` loop:
    * Extract the `passive_defenses` attributes for the targeted plant species.
2. **Caloric Attenuation**:
    * Apply the digestibility modifier to the transferred energy:

    $$\text{calories\_metabolized} = \Delta e \times \text{digestibility\_modifier}$$

    * Add `calories_metabolized` to the herbivore swarm's energy surplus rather than the raw $\Delta e$ eaten.
3. **Mechanical Damage**:
    * Compute mechanical damage:
        $$\text{damage\_taken} = \text{mechanical\_damage\_per\_bite} \times (1.0 - \text{swarm.resistances.get('mechanical', 0.0)})$$
    * Deduct `damage_taken` directly from the grazing swarm's population count ($n(t)$).

---

### Step 5: The Empirical Database Overhaul

**Target File:** `src/phids/analytics/bio_database.json`

1. Completely refactor the JSON database structure to group parameters cleanly:
    * `base_metrics` (growth, max energy, reproduction, etc.)
    * `passive_defenses` (mechanical damage, digestibility modifier)
    * `substances` (signals, toxins definitions)
    * `trigger_rules` (triggers mapping to substance synthesis or resource withdrawal actions)
2. Include realistic examples representing:
    * A multi-level warning cascade (e.g., Neighbor VOC -> Local signal -> Toxin synthesis).
    * A `resource_withdrawal` action triggering under high local herbivore density stress.

---

### Step 6: The "Morphology & Defense" UI Tab

**Target Files:** `src/phids/api/templates/partials/`

1. Create a separate HTMX partial `morphology_defense_tab.html`.
2. Render custom sliders for `Mechanical Damage` and `Digestibility Modifier`.
3. Expose an interactive trigger array editor supporting both action types (`synthesize_substance` and `resource_withdrawal`).
4. Add real-time warning indicators for invalid configurations (e.g., orphan signals that are emitted but never referenced in any trigger conditions).

---

## QA & Pre-Commit Validation

* **Fixed Dimension Matrix Boundary:** Verify that updates do not modify or bypass the $16 \times 16$ bounds configured in the `DietCompatibilityMatrix` or trigger rules.
* **Performance Verification:** Run pytest and typecheck to verify there are no performance regressions or Numba typing failures:

    ```bash
    uv run pytest
    uv run ruff check .
    ```
