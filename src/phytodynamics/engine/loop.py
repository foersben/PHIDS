"""Simulation loop orchestration with deterministic ticks.

This module implements the main simulation driver which advances the
grid environment and ECS world through ordered systems. It captures
per-tick snapshots for replay and telemetry and enforces deterministic
update ordering using an asyncio lock.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from phytodynamics.api.schemas import SimulationConfig
from phytodynamics.engine.components.plant import PlantComponent
from phytodynamics.engine.components.swarm import SwarmComponent
from phytodynamics.engine.core.biotope import GridEnvironment
from phytodynamics.engine.core.ecs import ECSWorld
from phytodynamics.engine.core.flow_field import apply_camouflage, compute_flow_field
from phytodynamics.engine.systems.interaction import run_interaction
from phytodynamics.engine.systems.lifecycle import run_lifecycle
from phytodynamics.engine.systems.signaling import run_signaling
from phytodynamics.io.replay import ReplayBuffer
from phytodynamics.telemetry.analytics import TelemetryRecorder
from phytodynamics.telemetry.conditions import TerminationResult, check_termination

logger = logging.getLogger(__name__)


class SimulationLoop:
    """Orchestrate deterministic, double-buffered simulation ticks.

    Double-buffering is achieved by keeping a read-copy of the grid state
    while writing results to live objects; these writes become the read
    state for the next tick. Concurrent access is protected by
    ``asyncio.Lock``.

    Args:
        config: Validated :class:`~phytodynamics.api.schemas.SimulationConfig`.
    """

    def __init__(self, config: SimulationConfig) -> None:
        """Initialise the SimulationLoop with the provided configuration.

        Args:
            config: Validated SimulationConfig instance from the API payload.
        """
        self.config = config
        self.tick: int = 0
        self.running: bool = False
        self.paused: bool = False
        self.terminated: bool = False
        self.termination_reason: str | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

        # Build environment
        self.env = GridEnvironment(
            width=config.grid_width,
            height=config.grid_height,
            num_signals=config.num_signals,
            num_toxins=config.num_toxins,
        )
        self.env.set_uniform_wind(config.wind_x, config.wind_y)

        # Build ECS
        self.world = ECSWorld()

        # Telemetry
        self.telemetry = TelemetryRecorder()
        # Deterministic replay state frames (msgpack serialisation per tick)
        self.replay = ReplayBuffer()

        # Pre-compute species parameter lookups
        self._flora_params: dict[int, Any] = {
            sp.species_id: sp for sp in config.flora_species
        }
        self._trigger_conditions: dict[int, list[Any]] = {
            sp.species_id: list(sp.triggers) for sp in config.flora_species
        }
        self._diet_matrix: list[list[bool]] = config.diet_matrix.rows

        # Spawn initial entities
        self._spawn_initial_entities()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _spawn_initial_entities(self) -> None:
        """Place initial plants and swarms from the configuration.

        The method creates entity instances, attaches components, registers
        spatial positions in the :class:`ECSWorld`, and populates the
        environment's plant energy buffers.
        """
        for placement in self.config.initial_plants:
            params = self._flora_params.get(placement.species_id)
            if params is None:
                continue
            entity = self.world.create_entity()
            plant = PlantComponent(
                entity_id=entity.entity_id,
                species_id=placement.species_id,
                x=placement.x,
                y=placement.y,
                energy=placement.energy,
                max_energy=params.max_energy,
                base_energy=params.base_energy,
                growth_rate=params.growth_rate,
                survival_threshold=params.survival_threshold,
                reproduction_interval=params.reproduction_interval,
                seed_min_dist=params.seed_min_dist,
                seed_max_dist=params.seed_max_dist,
                seed_energy_cost=params.seed_energy_cost,
                camouflage=params.camouflage,
                camouflage_factor=params.camouflage_factor,
            )
            self.world.add_component(entity.entity_id, plant)
            self.world.register_position(entity.entity_id, placement.x, placement.y)
            self.env.set_plant_energy(
                placement.x, placement.y, placement.species_id, placement.energy
            )

        for placement in self.config.initial_swarms:
            entity = self.world.create_entity()
            swarm = SwarmComponent(
                entity_id=entity.entity_id,
                species_id=placement.species_id,
                x=placement.x,
                y=placement.y,
                population=placement.population,
                initial_population=placement.population,
                energy=placement.energy,
                energy_min=self._get_predator_energy_min(placement.species_id),
                velocity=self._get_predator_velocity(placement.species_id),
                consumption_rate=self._get_predator_consumption_rate(placement.species_id),
            )
            self.world.add_component(entity.entity_id, swarm)
            self.world.register_position(entity.entity_id, placement.x, placement.y)

        self.env.rebuild_energy_layer()

    def _get_predator_energy_min(self, species_id: int) -> float:
        """Return the configured minimum energy for a predator species.

        Args:
            species_id: Predator species identifier to look up.

        Returns:
            float: Configured minimum energy if found, otherwise a sensible
            default of 1.0.
        """
        for sp in self.config.predator_species:
            if sp.species_id == species_id:
                return sp.energy_min
        return 1.0

    def _get_predator_velocity(self, species_id: int) -> int:
        """Return the configured movement period (velocity) for a predator.

        Args:
            species_id: Predator species identifier to look up.

        Returns:
            int: Movement period in ticks; defaults to 1 when not found.
        """
        for sp in self.config.predator_species:
            if sp.species_id == species_id:
                return sp.velocity
        return 1

    def _get_predator_consumption_rate(self, species_id: int) -> float:
        """Return the per-tick consumption rate for a predator species.

        Args:
            species_id: Predator species identifier to look up.

        Returns:
            float: Consumption rate if present, otherwise 1.0 by default.
        """
        for sp in self.config.predator_species:
            if sp.species_id == species_id:
                return sp.consumption_rate
        return 1.0

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the simulation as running.

        Sets running state to True and clears the paused flag.
        """
        self.running = True
        self.paused = False

    def pause(self) -> None:
        """Toggle the paused state.

        Flips the ``paused`` boolean.
        """
        self.paused = not self.paused

    def stop(self) -> None:
        """Halt the simulation by clearing the running flag."""
        self.running = False

    # ------------------------------------------------------------------
    # Core tick
    # ------------------------------------------------------------------

    async def step(self) -> TerminationResult:
        """Execute one deterministic simulation tick.

        The method performs the ordered phases of the simulation (flow-field
        update, lifecycle, interaction, signaling, telemetry) while holding
        an asyncio lock to ensure async-safety. After processing it
        evaluates termination conditions.

        Returns:
            TerminationResult: Termination state after the tick.
        """
        async with self._lock:
            if self.terminated:
                return TerminationResult(terminated=True, reason=self.termination_reason or "")

            # --------------------------------------------------------
            # Phase 1: Flow-field update (uses current read state)
            # --------------------------------------------------------
            self.env.flow_field = compute_flow_field(
                self.env.plant_energy_layer,
                self.env.toxin_layers,
                self.env.width,
                self.env.height,
            )

            # Apply camouflage attenuations
            for entity in self.world.query(PlantComponent):
                plant: PlantComponent = entity.get_component(PlantComponent)
                if plant.camouflage:
                    apply_camouflage(self.env.flow_field, plant.x, plant.y, plant.camouflage_factor)

            # --------------------------------------------------------
            # Phase 2: Lifecycle (grow, reproduce, cull)
            # --------------------------------------------------------
            run_lifecycle(self.world, self.env, self.tick, self._flora_params)

            # --------------------------------------------------------
            # Phase 3: Interaction (movement, feeding, starvation, mitosis)
            # --------------------------------------------------------
            run_interaction(self.world, self.env, self._diet_matrix, self.tick)

            # --------------------------------------------------------
            # Phase 4: Signaling (substance synthesis, diffusion, toxins)
            # --------------------------------------------------------
            run_signaling(
                self.world,
                self.env,
                self._trigger_conditions,
                self.config.mycorrhizal_inter_species,
                self.config.mycorrhizal_signal_velocity,
                self.tick,
            )

            # --------------------------------------------------------
            # Phase 5: Telemetry
            # --------------------------------------------------------
            self.telemetry.record(self.world, self.tick)
            self.replay.append(self.get_state_snapshot())

            # --------------------------------------------------------
            # Phase 6: Termination check (double-buffer swap happens here
            #          implicitly – all writes committed before check)
            # --------------------------------------------------------
            result = check_termination(
                self.world,
                self.tick,
                max_ticks=self.config.max_ticks,
                z2_flora_species=self.config.z2_flora_species_extinction,
                z4_predator_species=self.config.z4_predator_species_extinction,
                z6_max_flora_energy=self.config.z6_max_total_flora_energy,
                z7_max_predator_population=self.config.z7_max_total_predator_population,
            )

            self.tick += 1

            if result.terminated:
                self.terminated = True
                self.running = False
                self.termination_reason = result.reason
                logger.info("Simulation terminated at tick %d: %s", self.tick, result.reason)

            return result

    async def run(self) -> None:
        """Run the simulation loop until termination at configured tick rate.

        The loop respects ``paused`` and sleeps to maintain ``tick_rate_hz``.
        """
        import time

        tick_interval = 1.0 / self.config.tick_rate_hz
        self.start()

        while self.running and not self.terminated:
            if self.paused:
                await asyncio.sleep(tick_interval)
                continue

            t0 = time.monotonic()
            result = await self.step()
            if result.terminated:
                break
            elapsed = time.monotonic() - t0
            sleep_time = max(0.0, tick_interval - elapsed)
            await asyncio.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Wind update (REST API integration point)
    # ------------------------------------------------------------------

    def update_wind(self, vx: float, vy: float) -> None:
        """Update the environment uniform wind vector.

        Args:
            vx: Wind X component.
            vy: Wind Y component.
        """
        self.env.set_uniform_wind(vx, vy)

    # ------------------------------------------------------------------
    # State snapshot for WebSocket streaming
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return a serialisable snapshot of the current grid state.

        Returns:
            dict[str, Any]: Snapshot containing tick, termination state and
            environment dictionary (from :meth:`GridEnvironment.to_dict`).
        """
        return {
            "tick": self.tick,
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
            **self.env.to_dict(),
        }
