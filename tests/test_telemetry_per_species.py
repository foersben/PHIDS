"""Tests for per-species telemetry accumulation.

This test module validates that :class:`~phids.telemetry.analytics.TelemetryRecorder`
correctly accumulates per-species population, energy, and defense-cost metrics across
multi-species ECS worlds. The suite exercises the full data pathway from ECS entity
sampling through defaultdict accumulation to the final ``_rows`` list and the
:meth:`~phids.telemetry.analytics.TelemetryRecorder.get_species_ids` helper, ensuring
that downstream Chart.js serialisation and Polars DataFrame construction receive
correctly keyed and zeroed-filled data structures regardless of species cardinality.
"""

from __future__ import annotations

from phids.engine.components.plant import PlantComponent
from phids.engine.components.substances import SubstanceComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.ecs import ECSWorld
from phids.telemetry.analytics import TelemetryRecorder


def _make_plant(world: ECSWorld, eid: int, species_id: int, energy: float) -> None:
    """Register a minimal PlantComponent into the ECS world for testing."""
    world.add_component(
        eid,
        PlantComponent(
            entity_id=eid,
            species_id=species_id,
            x=0, y=0,
            energy=energy,
            max_energy=100.0,
            base_energy=50.0,
            growth_rate=1.0,
            survival_threshold=1.0,
            reproduction_interval=50,
            seed_min_dist=1.0,
            seed_max_dist=3.0,
            seed_energy_cost=10.0,
        ),
    )
    world.register_position(eid, 0, 0)


def _make_swarm(world: ECSWorld, eid: int, species_id: int, population: int) -> None:
    """Register a minimal SwarmComponent into the ECS world for testing."""
    world.add_component(
        eid,
        SwarmComponent(
            entity_id=eid,
            species_id=species_id,
            x=1, y=1,
            population=population,
            initial_population=population,
            energy=float(population * 5),
            energy_min=5.0,
            velocity=1,
            consumption_rate=1.0,
        ),
    )
    world.register_position(eid, 1, 1)


class TestPerSpeciesTelemetry:
    """Validates per-species accumulation in TelemetryRecorder."""

    def test_plant_population_by_species(self) -> None:
        """Per-species plant headcounts are correctly accumulated from ECS entities."""
        world = ECSWorld()
        e1 = world.create_entity()
        e2 = world.create_entity()
        e3 = world.create_entity()
        _make_plant(world, e1.entity_id, 0, 30.0)
        _make_plant(world, e2.entity_id, 0, 40.0)
        _make_plant(world, e3.entity_id, 1, 20.0)

        rec = TelemetryRecorder()
        rec.record(world, tick=1)

        row = rec.get_latest_metrics()
        assert row is not None
        assert row["flora_population"] == 3
        assert row["plant_pop_by_species"][0] == 2
        assert row["plant_pop_by_species"][1] == 1

    def test_plant_energy_by_species(self) -> None:
        """Per-species aggregate energy is summed correctly over all co-species plants."""
        world = ECSWorld()
        e1 = world.create_entity()
        e2 = world.create_entity()
        _make_plant(world, e1.entity_id, 0, 25.0)
        _make_plant(world, e2.entity_id, 0, 35.0)

        rec = TelemetryRecorder()
        rec.record(world, tick=0)

        row = rec.get_latest_metrics()
        assert row is not None
        assert abs(row["plant_energy_by_species"][0] - 60.0) < 1e-6

    def test_swarm_population_by_species(self) -> None:
        """Per-species predator headcounts accumulate all individuals across all clusters."""
        world = ECSWorld()
        e1 = world.create_entity()
        e2 = world.create_entity()
        e3 = world.create_entity()
        _make_swarm(world, e1.entity_id, 0, 100)
        _make_swarm(world, e2.entity_id, 0, 50)
        _make_swarm(world, e3.entity_id, 1, 200)

        rec = TelemetryRecorder()
        rec.record(world, tick=0)

        row = rec.get_latest_metrics()
        assert row is not None
        assert row["swarm_pop_by_species"][0] == 150
        assert row["swarm_pop_by_species"][1] == 200

    def test_defense_cost_by_species(self) -> None:
        """Active substance energy costs are attributed to the correct flora species."""
        world = ECSWorld()
        pe = world.create_entity()
        _make_plant(world, pe.entity_id, 0, 80.0)

        # Create an active substance owned by the plant
        se = world.create_entity()
        world.add_component(
            se.entity_id,
            SubstanceComponent(
                entity_id=se.entity_id,
                substance_id=0,
                owner_plant_id=pe.entity_id,
                is_toxin=False,
                active=True,
                energy_cost_per_tick=2.5,
            ),
        )

        rec = TelemetryRecorder()
        rec.record(world, tick=0)

        row = rec.get_latest_metrics()
        assert row is not None
        assert abs(row["defense_cost_by_species"].get(0, 0.0) - 2.5) < 1e-6

    def test_get_species_ids_accumulates_across_ticks(self) -> None:
        """get_species_ids returns the union of all species seen across the full history."""
        world = ECSWorld()
        e1 = world.create_entity()
        _make_plant(world, e1.entity_id, 0, 10.0)

        rec = TelemetryRecorder()
        rec.record(world, tick=0)

        # Kill species 0 plant, add species 1 plant
        world.collect_garbage([e1.entity_id])
        e2 = world.create_entity()
        _make_plant(world, e2.entity_id, 1, 20.0)
        rec.record(world, tick=1)

        ids = rec.get_species_ids()
        assert 0 in ids["flora_ids"]
        assert 1 in ids["flora_ids"]

    def test_dataframe_excludes_nested_dicts(self) -> None:
        """The Polars DataFrame contains only scalar columns, not nested dict columns."""
        world = ECSWorld()
        e1 = world.create_entity()
        _make_plant(world, e1.entity_id, 0, 50.0)

        rec = TelemetryRecorder()
        rec.record(world, tick=0)

        df = rec.dataframe
        assert "tick" in df.columns
        assert "flora_population" in df.columns
        # Nested dict columns must not be present in the Polars frame
        assert "plant_pop_by_species" not in df.columns

    def test_empty_recorder_returns_empty_dataframe(self) -> None:
        """An unrecorded TelemetryRecorder returns an empty well-typed Polars DataFrame."""
        rec = TelemetryRecorder()
        df = rec.dataframe
        assert df.height == 0
        assert "tick" in df.columns

    def test_reset_clears_rows(self) -> None:
        """reset() empties _rows and invalidates the cached DataFrame."""
        world = ECSWorld()
        rec = TelemetryRecorder()
        rec.record(world, tick=0)
        assert len(rec._rows) == 1
        rec.reset()
        assert len(rec._rows) == 0
        assert rec._df is None

    def test_buffer_cap_retains_only_latest_ticks(self) -> None:
        """TelemetryRecorder enforces FIFO retention once max_rows is exceeded."""
        world = ECSWorld()
        rec = TelemetryRecorder(max_rows=3)
        for tick in range(6):
            rec.record(world, tick=tick)
        assert len(rec._rows) == 3
        assert [row["tick"] for row in rec._rows] == [3, 4, 5]

