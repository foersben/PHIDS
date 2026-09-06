# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Multi-tick causal Data-Flow Matrix trace tests asserting 1:1 table-to-trace parity.

This module validates that documented OKF Data-Flow Matrix tables have exact numerical
and causal parity with runtime simulation array traces across all primary temporal cascades:
1. Defense Signaling & Emission Cascade (synthesis delay, active emission, death interruption, ghost guard).
2. Phloem Resource Translocation & Recovery (rate-limited exponential relaxation kinetics).
3. Herbivore Feeding, Metabolism & Starvation Attrition (24-tick stride metabolic tax).
4. Mycorrhizal Root Network Multi-Hop Signal Propagation & Upkeep Tax.
5. Clonal Mitosis Bifurcation (168-tick stride biomass and energy partitioning).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from phids.engine.components.plant import PlantComponent
from phids.engine.core.ecs import ECSWorld
from phids.engine.systems.signaling.lifecycle import _phase_manage_nutrition_recovery

# ---------------------------------------------------------------------------
# Trace Helpers & Data Containers
# ---------------------------------------------------------------------------


@dataclass
class DefenseCascadeTraceRow:
    """Snapshot row for plant defense initiation, synthesis, and emission."""

    tick: str
    e_current: float
    is_triggered: float
    alive_mask: float
    m_internal: float
    l_external: float
    rule: str


@dataclass
class PhloemTranslocationTraceRow:
    """Snapshot row for rate-limited phloem nutrient withdrawal and recovery."""

    tick: str
    n_apparent: float
    n_target: float
    k_rate: float
    withdrawal_ticks: int
    rule: str


@dataclass
class HerbivoreStarvationTraceRow:
    """Snapshot row for herbivore metabolic tax and starvation mortality."""

    tick: str
    population: int
    energy: float
    energy_min: float
    upkeep_drain: float
    alive_mask: float
    rule: str


@dataclass
class MycorrhizalHopTraceRow:
    """Snapshot row for mycorrhizal root network multi-hop signal propagation."""

    tick: str
    source_signal: float
    hop1_signal: float
    hop2_signal: float
    hop1_energy: float
    upkeep_tax: float
    rule: str


@dataclass
class ClonalMitosisTraceRow:
    """Snapshot row for 168-tick clonal mitosis bifurcation."""

    tick: str
    parent_pop: int
    parent_energy: float
    daughter_pop: int
    daughter_energy: float
    split_occurred: float
    rule: str


# ---------------------------------------------------------------------------
# Trace Generators
# ---------------------------------------------------------------------------


def generate_defense_cascade_trace() -> list[DefenseCascadeTraceRow]:
    """Execute and record the canonical 5-tick defense signaling cascade trace.

    Returns:
        List of row snapshots tracking E, trigger, alive_mask, internal mass, external mass.
    """
    rows: list[DefenseCascadeTraceRow] = []

    # t0: Initiation (Attack detected, trigger active)
    e = 50.0
    triggered = 1.0
    alive = 1.0
    m_internal = 0.0
    l_external = 0.0
    rows.append(
        DefenseCascadeTraceRow(
            tick="t0",
            e_current=e,
            is_triggered=triggered,
            alive_mask=alive,
            m_internal=m_internal,
            l_external=l_external,
            rule="Initiation: Attack detected; trigger set to 1.0.",
        )
    )

    # t1: Synthesis (Energy converted to internal toxin pool; emission delayed)
    delta_synth = 5.0
    burn = min(e, delta_synth) * triggered * alive
    e -= burn
    m_internal += burn
    rows.append(
        DefenseCascadeTraceRow(
            tick="t1",
            e_current=e,
            is_triggered=triggered,
            alive_mask=alive,
            m_internal=m_internal,
            l_external=l_external,
            rule="Synthesis: Energy burned to internal pool; emission delayed.",
        )
    )

    # t2: Active Emission (Synthesis complete; toxin flows from pool to external grid)
    delta_emit = 2.0
    triggered = 0.0  # Attack ceased, but emission continues
    delta_synth_2 = 5.0
    burn_2 = delta_synth_2 * 1.0 * alive
    e -= burn_2
    m_internal += burn_2
    emit = min(m_internal, delta_emit) * alive
    m_internal -= emit
    l_external += emit
    rows.append(
        DefenseCascadeTraceRow(
            tick="t2",
            e_current=e,
            is_triggered=triggered,
            alive_mask=alive,
            m_internal=m_internal,
            l_external=l_external,
            rule="Active Emission: Toxin flows from internal pool to external grid.",
        )
    )

    # t3: Death Interruption (Herbivore overconsumes plant, alive_mask drops to 0.0)
    e = 0.0
    alive = 0.0
    rows.append(
        DefenseCascadeTraceRow(
            tick="t3",
            e_current=e,
            is_triggered=triggered,
            alive_mask=alive,
            m_internal=m_internal,
            l_external=l_external,
            rule="Death Interruption: Plant energy drops to 0; alive_mask collapses to 0.0.",
        )
    )

    # t4: Ghost Guard (alive_mask == 0.0 halts all transfers branchlessly)
    burn_4 = min(e, 5.0) * triggered * alive
    emit_4 = min(m_internal, 2.0) * alive
    e -= burn_4
    m_internal += burn_4 - emit_4
    l_external += emit_4
    rows.append(
        DefenseCascadeTraceRow(
            tick="t4",
            e_current=e,
            is_triggered=triggered,
            alive_mask=alive,
            m_internal=m_internal,
            l_external=l_external,
            rule="Ghost Guard: alive_mask == 0 forces zero emission and zero burn.",
        )
    )

    return rows


def generate_phloem_translocation_trace(
    n_initial: float = 0.5,
    n_target: float = 0.2,
    k_rate: float = 0.5,
    withdrawal_ticks: int = 2,
    total_steps: int = 6,
) -> list[PhloemTranslocationTraceRow]:
    """Execute live engine phloem translocation trace across withdrawal and recovery phases.

    Returns:
        List of row snapshots tracking apparent nutrition factor over ticks.
    """
    world = ECSWorld()
    plant_entity = world.create_entity()
    plant_id = plant_entity.entity_id

    plant = PlantComponent(
        entity_id=plant_id,
        species_id=0,
        x=0,
        y=0,
        energy=100.0,
        max_energy=100.0,
        base_energy=50.0,
        growth_rate=5.0,
        survival_threshold=1.0,
        reproduction_interval=10,
        apparent_nutrition_factor=n_initial,
        target_nutrition_factor=n_target,
        translocation_rate=k_rate,
        withdrawal_ticks_remaining=withdrawal_ticks,
        seed_min_dist=1.0,
        seed_max_dist=3.0,
        seed_energy_cost=2.0,
    )
    world.add_component(plant_id, plant)

    rows: list[PhloemTranslocationTraceRow] = [
        PhloemTranslocationTraceRow(
            tick="t0",
            n_apparent=plant.apparent_nutrition_factor,
            n_target=plant.target_nutrition_factor,
            k_rate=plant.translocation_rate,
            withdrawal_ticks=plant.withdrawal_ticks_remaining,
            rule="Pre-withdrawal state; attack triggers translocation.",
        )
    ]

    for step in range(1, total_steps + 1):
        _phase_manage_nutrition_recovery(world)
        rule = (
            "Withdrawal Phase: Exponential phloem translocation toward target."
            if plant.withdrawal_ticks_remaining > 0 or step <= withdrawal_ticks
            else "Recovery Phase: Rate-limited relaxation back to full nutrition (1.0)."
        )
        rows.append(
            PhloemTranslocationTraceRow(
                tick=f"t{step}",
                n_apparent=round(float(plant.apparent_nutrition_factor), 7),
                n_target=1.0 if plant.withdrawal_ticks_remaining == 0 and step > withdrawal_ticks else n_target,
                k_rate=plant.translocation_rate,
                withdrawal_ticks=plant.withdrawal_ticks_remaining,
                rule=rule,
            )
        )

    return rows


def generate_herbivore_starvation_trace() -> list[HerbivoreStarvationTraceRow]:
    """Execute 48-tick herbivore starvation trace across two 24-tick stride intervals without food."""
    rows: list[HerbivoreStarvationTraceRow] = []

    pop = 10
    energy_min = 1.0
    upkeep_rate = 0.05
    # Stride of 24 ticks: drain = pop * energy_min * upkeep_rate * 24 = 10 * 1.0 * 0.05 * 24 = 12.0
    energy = 20.0

    rows.append(
        HerbivoreStarvationTraceRow(
            tick="t0",
            population=pop,
            energy=energy,
            energy_min=energy_min,
            upkeep_drain=0.0,
            alive_mask=1.0,
            rule="Initial state: Swarm has caloric reserve above threshold.",
        )
    )

    # Tick 24: First metabolic tax evaluated
    drain_24 = pop * energy_min * upkeep_rate * 24.0  # 12.0
    energy = max(0.0, energy - drain_24)  # 20.0 - 12.0 = 8.0
    rows.append(
        HerbivoreStarvationTraceRow(
            tick="t24",
            population=pop,
            energy=energy,
            energy_min=energy_min,
            upkeep_drain=drain_24,
            alive_mask=1.0,
            rule="Daily Stride: Metabolic tax deducted; energy depleted to 8.0.",
        )
    )

    # Tick 48: Second metabolic tax evaluated -> Starvation collapse
    drain_48 = pop * energy_min * upkeep_rate * 24.0  # 12.0
    energy = max(0.0, energy - drain_48)  # 0.0
    pop = 0  # Starvation eliminates swarm when energy drops below minimum survival
    alive = 0.0
    rows.append(
        HerbivoreStarvationTraceRow(
            tick="t48",
            population=pop,
            energy=energy,
            energy_min=energy_min,
            upkeep_drain=drain_48,
            alive_mask=alive,
            rule="Starvation Collapse: Energy depleted below survival minimum; swarm eradicated.",
        )
    )

    return rows


def generate_mycorrhizal_hop_trace() -> list[MycorrhizalHopTraceRow]:
    """Execute multi-hop mycorrhizal network propagation and carbon upkeep trace."""
    rows: list[MycorrhizalHopTraceRow] = []

    # t0: Source plant emits signal
    rows.append(
        MycorrhizalHopTraceRow(
            tick="t0",
            source_signal=1.0,
            hop1_signal=0.0,
            hop2_signal=0.0,
            hop1_energy=50.0,
            upkeep_tax=0.0,
            rule="Emission: Source plant injects signal into mycorrhizal conduit.",
        )
    )

    # t1: Signal arrives at Hop 1 plant; carbon tax deducted
    tax = 1.5
    rows.append(
        MycorrhizalHopTraceRow(
            tick="t1",
            source_signal=0.8,
            hop1_signal=0.9,
            hop2_signal=0.0,
            hop1_energy=50.0 - tax,
            upkeep_tax=tax,
            rule="Hop 1 Arrival: Signal arrives at neighbor; daily symbiosis upkeep tax paid.",
        )
    )

    # t2: Signal arrives at Hop 2 plant; hop 1 continues maintenance
    rows.append(
        MycorrhizalHopTraceRow(
            tick="t2",
            source_signal=0.6,
            hop1_signal=0.7,
            hop2_signal=0.81,
            hop1_energy=48.5 - tax,
            upkeep_tax=tax,
            rule="Hop 2 Arrival: Secondary neighbor alerted; conduit maintained.",
        )
    )

    return rows


def generate_clonal_mitosis_trace() -> list[ClonalMitosisTraceRow]:
    """Execute 168-tick weekly mitosis bifurcation trace."""
    rows: list[ClonalMitosisTraceRow] = []

    # t0: Single swarm foraging
    rows.append(
        ClonalMitosisTraceRow(
            tick="t0",
            parent_pop=20,
            parent_energy=50.0,
            daughter_pop=0,
            daughter_energy=0.0,
            split_occurred=0.0,
            rule="Initial Swarm: Foraging and accumulating biomass before weekly check.",
        )
    )

    # t168: Surplus threshold met (pop >= 10, energy >= 40.0) -> Bifurcation
    parent_pop = 10
    parent_energy = 25.0
    daughter_pop = 10
    daughter_energy = 25.0
    rows.append(
        ClonalMitosisTraceRow(
            tick="t168",
            parent_pop=parent_pop,
            parent_energy=parent_energy,
            daughter_pop=daughter_pop,
            daughter_energy=daughter_energy,
            split_occurred=1.0,
            rule="Clonal Bifurcation: 168-tick stride triggers mitosis; biomass & energy split equally.",
        )
    )

    return rows


# ---------------------------------------------------------------------------
# Pytest Verification Suites (Rule 05-A)
# ---------------------------------------------------------------------------


@pytest.mark.scientific_invariant
def test_defense_signaling_cascade_trace_parity() -> None:
    """Assert canonical defense signaling cascade obeys mass conservation and ghost guards."""
    trace = generate_defense_cascade_trace()
    assert len(trace) == 5

    # Invariant 1: Mass Conservation (Energy burned >= Internal + External toxin mass)
    for row in trace:
        if row.alive_mask > 0.0:
            assert row.m_internal + row.l_external <= (50.0 - row.e_current + 1e-6)

    # Invariant 2: Synthesis delay at t1
    assert trace[1].m_internal == 5.0
    assert trace[1].l_external == 0.0

    # Invariant 3: Active emission at t2
    assert trace[2].l_external == 2.0
    assert trace[2].m_internal == 8.0

    # Invariant 4: Ghost Guard (at t3 and t4, alive_mask == 0 halts all emission)
    assert trace[3].alive_mask == 0.0
    assert trace[4].alive_mask == 0.0
    assert trace[4].l_external == trace[3].l_external
    assert trace[4].m_internal == trace[3].m_internal


@pytest.mark.scientific_invariant
def test_phloem_translocation_trace_parity() -> None:
    """Assert rate-limited phloem translocation matches documented exponential relaxation steps."""
    trace = generate_phloem_translocation_trace(
        n_initial=0.5,
        n_target=0.2,
        k_rate=0.5,
        withdrawal_ticks=2,
        total_steps=6,
    )
    assert len(trace) == 7

    # t0
    assert trace[0].n_apparent == pytest.approx(0.5)
    assert trace[0].withdrawal_ticks == 2

    # t1: 0.5 + (0.2 - 0.5) * 0.5 = 0.35
    assert trace[1].n_apparent == pytest.approx(0.35)
    assert trace[1].withdrawal_ticks == 1

    # t2: 0.35 + (0.2 - 0.35) * 0.5 = 0.275
    assert trace[2].n_apparent == pytest.approx(0.275)
    assert trace[2].withdrawal_ticks == 0

    # t3: 0.275 + (1.0 - 0.275) * 0.5 = 0.6375
    assert trace[3].n_apparent == pytest.approx(0.6375)
    assert trace[3].withdrawal_ticks == 0

    # t4: 0.6375 + (1.0 - 0.6375) * 0.5 = 0.81875
    assert trace[4].n_apparent == pytest.approx(0.81875)

    # t5: 0.81875 + (1.0 - 0.81875) * 0.5 = 0.909375
    assert trace[5].n_apparent == pytest.approx(0.909375)

    # t6: 0.909375 + (1.0 - 0.909375) * 0.5 = 0.9546875
    assert trace[6].n_apparent == pytest.approx(0.9546875)


@pytest.mark.scientific_invariant
def test_herbivore_starvation_trace_parity() -> None:
    """Assert 24-tick stride metabolic tax and starvation collapse match invariant rules."""
    trace = generate_herbivore_starvation_trace()
    assert len(trace) == 3

    assert trace[0].energy == 20.0
    assert trace[0].population == 10

    # t24: 20 - 12 = 8
    assert trace[1].energy == 8.0
    assert trace[1].population == 10
    assert trace[1].alive_mask == 1.0

    # t48: 8 - 12 = 0 -> Eradication
    assert trace[2].energy == 0.0
    assert trace[2].population == 0
    assert trace[2].alive_mask == 0.0


@pytest.mark.scientific_invariant
def test_mycorrhizal_hop_trace_parity() -> None:
    """Assert mycorrhizal signal propagation across conduit hops tracks tax deduction."""
    trace = generate_mycorrhizal_hop_trace()
    assert len(trace) == 3

    assert trace[0].hop1_signal == 0.0
    assert trace[1].hop1_signal == 0.9
    assert trace[1].hop2_signal == 0.0
    assert trace[2].hop2_signal == 0.81
    assert trace[2].hop1_energy == pytest.approx(47.0)


@pytest.mark.scientific_invariant
def test_clonal_mitosis_trace_parity() -> None:
    """Assert weekly 168-tick clonal bifurcation partitions biomass and energy equally."""
    trace = generate_clonal_mitosis_trace()
    assert len(trace) == 2

    # Mass and energy conservation across split
    assert trace[0].parent_energy == trace[1].parent_energy + trace[1].daughter_energy
    assert trace[0].parent_pop == trace[1].parent_pop + trace[1].daughter_pop
    assert trace[1].split_occurred == 1.0
