"""Simulation loop orchestration for deterministic, double-buffered ecosystem advancement.

This module implements the principal simulation driver for PHIDS, responsible for advancing the
grid environment and ECS world through a rigorously ordered sequence of systems: flow field,
lifecycle, interaction, signaling, and telemetry/termination. The simulation loop enforces
deterministic update ordering via an ``asyncio.Lock``, ensuring reproducibility and scientific
validity. Double-buffering is employed to maintain a strict separation between read and write
states, preventing race conditions and guaranteeing the integrity of biological phenomena such as
systemic acquired resistance, metabolic attrition, and mitosis. Per-tick snapshots are captured
for replay and telemetry, supporting comprehensive analysis of emergent behaviours and ecological
dynamics. The architectural design reflects the project's commitment to data-oriented modelling,
O(1) spatial hash lookups, and the Rule of 16 for memory allocation, thereby simulating complex
plant-herbivore interactions with maximal computational efficiency and biological fidelity.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from phids.api.schemas import SimulationConfig
from phids.engine.components.plant import PlantComponent
from phids.engine.components.swarm import SwarmComponent
from phids.engine.core.biotope import GridEnvironment
from phids.engine.core.ecs import ECSWorld
from phids.engine.core.flow_field import apply_camouflage, compute_flow_field
from phids.engine.systems.interaction import run_interaction
from phids.engine.systems.lifecycle import run_lifecycle
from phids.engine.systems.signaling import run_signaling
from phids.io.replay import ReplayBuffer
from phids.shared.constants import MAX_REPLAY_FRAMES
from phids.telemetry.analytics import TelemetryRecorder
from phids.telemetry.conditions import TerminationResult, check_termination
from phids.telemetry.tick_metrics import TickMetrics, collect_tick_metrics
from phids.shared.logging_config import get_simulation_debug_interval

# Optional Zarr backend import
try:
    from phids.io.zarr_replay import ZarrReplayBuffer as _ImportedZarrReplayBuffer

    _ZarrReplayBuffer: type[Any] | None = _ImportedZarrReplayBuffer
except ImportError:
    _ZarrReplayBuffer = None

logger = logging.getLogger(__name__)


class SimulationLoop:
    """Orchestrate deterministic, double-buffered simulation ticks.

    Double-buffering is achieved by keeping a read-copy of the grid state
    while writing results to live objects; these writes become the read
    state for the next tick. Concurrent access is protected by
    ``asyncio.Lock``.

    Args:
        config: Validated :class:`~phids.api.schemas.SimulationConfig`.
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
        self._debug_tick_interval: int = get_simulation_debug_interval()
        self._cached_snapshot_tick: int = -1
        self._cached_snapshot: dict[str, Any] | None = None

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
        # Deterministic replay state frames; backend selected by config
        self.replay: Any
        if config.replay_backend == "zarr" and _ZarrReplayBuffer is not None:
            self.replay = _ZarrReplayBuffer(max_frames=MAX_REPLAY_FRAMES)
            logger.info("Using Zarr replay backend (max_frames=%d)", MAX_REPLAY_FRAMES)
        else:
            self.replay = ReplayBuffer(max_frames=MAX_REPLAY_FRAMES, spill_to_disk=True)
            if config.replay_backend == "zarr":
                logger.warning(
                    "Zarr backend requested but unavailable; falling back to msgpack. "
                    "Install zarr with: uv add zarr"
                )

        # Pre-compute species parameter lookups
        self._flora_params: dict[int, Any] = {sp.species_id: sp for sp in config.flora_species}
        self._herbivore_params: dict[int, Any] = {
            sp.species_id: sp for sp in config.herbivore_species
        }
        self._trigger_conditions: dict[int, list[Any]] = {
            sp.species_id: list(sp.triggers) for sp in config.flora_species
        }
        self._diet_matrix: list[list[bool]] = config.diet_matrix.rows

        # Spawn initial entities
        self._spawn_initial_entities()
        logger.info(
            "SimulationLoop initialised (grid=%dx%d, flora_species=%d, herbivore_species=%d, signals=%d, toxins=%d, tick_rate_hz=%.2f)",
            config.grid_width,
            config.grid_height,
            len(config.flora_species),
            len(config.herbivore_species),
            config.num_signals,
            config.num_toxins,
            config.tick_rate_hz,
        )

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _spawn_initial_entities(self) -> None:
        """Place initial plants and swarms from the configuration.

        The method creates entity instances, attaches components, registers
        spatial positions in the :class:`ECSWorld`, and populates the
        environment's plant energy buffers.
        """
        spawned_plants = 0
        spawned_swarms = 0

        for plant_placement in self.config.initial_plants:
            params = self._flora_params.get(plant_placement.species_id)
            if params is None:
                logger.warning(
                    "Skipping initial plant placement with unknown flora species_id=%d at (%d, %d)",
                    plant_placement.species_id,
                    plant_placement.x,
                    plant_placement.y,
                )
                continue
            entity = self.world.create_entity()
            plant = PlantComponent(
                entity_id=entity.entity_id,
                species_id=plant_placement.species_id,
                x=plant_placement.x,
                y=plant_placement.y,
                energy=plant_placement.energy,
                max_energy=params.max_energy,
                base_energy=params.base_energy,
                growth_rate=params.growth_rate,
                survival_threshold=params.survival_threshold,
                reproduction_interval=params.reproduction_interval,
                seed_min_dist=params.seed_min_dist,
                seed_max_dist=params.seed_max_dist,
                seed_energy_cost=params.seed_energy_cost,
                seed_drop_height=params.seed_drop_height,
                seed_terminal_velocity=params.seed_terminal_velocity,
                camouflage=params.camouflage,
                camouflage_factor=params.camouflage_factor,
            )
            self.world.add_component(entity.entity_id, plant)
            self.world.register_position(entity.entity_id, plant_placement.x, plant_placement.y)
            self.env.set_plant_energy(
                plant_placement.x,
                plant_placement.y,
                plant_placement.species_id,
                plant_placement.energy,
            )
            spawned_plants += 1

        for swarm_placement in self.config.initial_swarms:
            entity = self.world.create_entity()
            swarm = SwarmComponent(
                entity_id=entity.entity_id,
                species_id=swarm_placement.species_id,
                x=swarm_placement.x,
                y=swarm_placement.y,
                population=swarm_placement.population,
                initial_population=swarm_placement.population,
                energy=swarm_placement.energy,
                energy_min=self._get_herbivore_energy_min(swarm_placement.species_id),
                velocity=self._get_herbivore_velocity(swarm_placement.species_id),
                consumption_rate=self._get_herbivore_consumption_rate(swarm_placement.species_id),
                reproduction_energy_divisor=self._get_herbivore_reproduction_divisor(
                    swarm_placement.species_id
                ),
                energy_upkeep_per_individual=self._get_herbivore_energy_upkeep(
                    swarm_placement.species_id
                ),
                split_population_threshold=self._get_herbivore_split_threshold(
                    swarm_placement.species_id
                ),
            )
            self.world.add_component(entity.entity_id, swarm)
            self.world.register_position(entity.entity_id, swarm_placement.x, swarm_placement.y)
            spawned_swarms += 1

        self.env.rebuild_energy_layer()
        logger.info(
            "Initial entities spawned (plants=%d, swarms=%d)",
            spawned_plants,
            spawned_swarms,
        )

    def _get_herbivore_energy_min(self, species_id: int) -> float:
        """Return the configured minimum energy for a herbivore species.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            float: Configured minimum energy if found, otherwise a sensible
            default of 1.0.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return float(params.energy_min)
        return 1.0

    def _get_herbivore_velocity(self, species_id: int) -> int:
        """Return the configured movement period (velocity) for a herbivore.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            int: Movement period in ticks; defaults to 1 when not found.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return int(params.velocity)
        return 1

    def _get_herbivore_consumption_rate(self, species_id: int) -> float:
        """Return the per-tick consumption rate for a herbivore species.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            float: Consumption rate if present, otherwise 1.0 by default.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return float(params.consumption_rate)
        return 1.0

    def _get_herbivore_reproduction_divisor(self, species_id: int) -> float:
        """Return the configured reproduction divisor for a herbivore species.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            float: Reproduction divisor if present, otherwise 1.0.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return float(params.reproduction_energy_divisor)
        return 1.0

    def _get_herbivore_energy_upkeep(self, species_id: int) -> float:
        """Return the configured per-individual metabolic upkeep scalar for a herbivore species.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            Configured upkeep scalar if found; otherwise 0.05 as a sensible default.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return float(params.energy_upkeep_per_individual)
        return 0.05

    def _get_herbivore_split_threshold(self, species_id: int) -> int:
        """Return the configured explicit mitosis population threshold for a herbivore species.

        Args:
            species_id: Herbivore species identifier to look up.

        Returns:
            Configured split threshold if found; otherwise 0, which causes the interaction
            system to apply the legacy initial-population-based mitosis rule.
        """
        params = self._herbivore_params.get(species_id)
        if params is not None:
            return int(params.split_population_threshold)
        return 0

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mark the simulation as running.

        Sets running state to True and clears the paused flag.
        """
        self.running = True
        self.paused = False
        logger.info("Simulation loop started/resumed at tick %d", self.tick)

    def pause(self) -> None:
        """Toggle the paused state.

        Flips the ``paused`` boolean.
        """
        self.paused = not self.paused
        logger.info(
            "Simulation loop %s at tick %d", "paused" if self.paused else "resumed", self.tick
        )

    def stop(self) -> None:
        """Halt the simulation by clearing the running flag."""
        self.running = False
        logger.info("Simulation loop stopped at tick %d", self.tick)

    def _should_log_debug_summary(self) -> bool:
        """Return whether the current tick should emit a DEBUG summary."""
        return (
            logger.isEnabledFor(logging.DEBUG)
            and self._debug_tick_interval > 0
            and self.tick % self._debug_tick_interval == 0
        )

    def _log_debug_tick_summary(
        self,
        *,
        latest_metrics: dict[str, Any] | None,
        phase_timings_ms: dict[str, float],
    ) -> None:
        """Emit a coarse DEBUG snapshot for the current tick."""
        swarm_population = 0
        for entity in self.world.query(SwarmComponent):
            swarm_population += entity.get_component(SwarmComponent).population

        logger.debug(
            (
                "Tick summary (tick=%d, flora_energy=%.3f, flora_population=%d, "
                "herbivore_clusters=%d, herbivore_population=%d, replay_frames=%d, "
                "phase_timings_ms=%s)"
            ),
            self.tick,
            float(latest_metrics.get("total_flora_energy", 0.0)) if latest_metrics else 0.0,
            int(latest_metrics.get("flora_population", 0)) if latest_metrics else 0,
            int(latest_metrics.get("herbivore_clusters", 0)) if latest_metrics else 0,
            swarm_population,
            len(self.replay),
            phase_timings_ms,
        )

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
                logger.debug(
                    "Simulation step skipped because loop is already terminated at tick %d",
                    self.tick,
                )
                return TerminationResult(terminated=True, reason=self.termination_reason or "")

            debug_summary = self._should_log_debug_summary()
            phase_timings_ms: dict[str, float] = {}
            plant_death_causes = {
                "death_reproduction": 0,
                "death_mycorrhiza": 0,
                "death_defense_maintenance": 0,
                "death_herbivore_feeding": 0,
                "death_background_deficit": 0,
            }
            phase_started = time.perf_counter()

            # --------------------------------------------------------
            # Phase 1: Flow-field update (uses current read state)
            # --------------------------------------------------------
            self.env.flow_field = compute_flow_field(
                self.env.plant_energy_layer,
                self.env.toxin_layers,
                self.env.width,
                self.env.height,
            )
            if debug_summary:
                phase_timings_ms["flow_field"] = (time.perf_counter() - phase_started) * 1000.0
                phase_started = time.perf_counter()

            # Apply camouflage attenuations
            for entity in self.world.query(PlantComponent):
                plant: PlantComponent = entity.get_component(PlantComponent)
                if plant.camouflage:
                    apply_camouflage(self.env.flow_field, plant.x, plant.y, plant.camouflage_factor)

            # --------------------------------------------------------
            # Phase 2: Lifecycle (grow, connect, reproduce, cull)
            # --------------------------------------------------------
            run_lifecycle(
                self.world,
                self.env,
                self.tick,
                self._flora_params,
                mycorrhizal_connection_cost=self.config.mycorrhizal_connection_cost,
                mycorrhizal_growth_interval_ticks=self.config.mycorrhizal_growth_interval_ticks,
                mycorrhizal_inter_species=self.config.mycorrhizal_inter_species,
                plant_death_causes=plant_death_causes,
            )
            if debug_summary:
                phase_timings_ms["lifecycle"] = (time.perf_counter() - phase_started) * 1000.0
                phase_started = time.perf_counter()

            # --------------------------------------------------------
            # Phase 3: Interaction (movement, feeding, starvation, mitosis)
            # --------------------------------------------------------
            run_interaction(
                self.world,
                self.env,
                self._diet_matrix,
                self.tick,
                plant_death_causes=plant_death_causes,
            )
            if debug_summary:
                phase_timings_ms["interaction"] = (time.perf_counter() - phase_started) * 1000.0
                phase_started = time.perf_counter()

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
                plant_death_causes=plant_death_causes,
            )
            if debug_summary:
                phase_timings_ms["signaling"] = (time.perf_counter() - phase_started) * 1000.0
                phase_started = time.perf_counter()

            # FIX: Commit all energy depletion from feeding and defense upkeep
            # before telemetry reads it and the next tick's flow field evaluates it.
            self.env.rebuild_energy_layer()

            # Build one shared metrics snapshot for telemetry and termination.
            tick_metrics: TickMetrics = collect_tick_metrics(self.world)

            # --------------------------------------------------------
            # Phase 5: Telemetry
            # --------------------------------------------------------
            self.telemetry.record(
                self.world,
                self.tick,
                plant_death_causes=plant_death_causes,
                tick_metrics=tick_metrics,
            )
            if hasattr(self.replay, "append_raw_arrays"):
                self.replay.append_raw_arrays(
                    tick=self.tick,
                    env=self.env,
                    termination_state=(self.terminated, self.termination_reason),
                )
            else:
                self.replay.append(self.get_state_snapshot())
            latest_metrics = self.telemetry.get_latest_metrics()
            if debug_summary:
                phase_timings_ms["telemetry_replay"] = (
                    time.perf_counter() - phase_started
                ) * 1000.0
                phase_started = time.perf_counter()

            # --------------------------------------------------------
            # Phase 6: Termination check (double-buffer swap happens here
            #          implicitly – all writes committed before check)
            # --------------------------------------------------------
            result = check_termination(
                self.world,
                self.tick,
                max_ticks=self.config.max_ticks,
                z2_flora_species=self.config.z2_flora_species_extinction,
                z4_herbivore_species=self.config.z4_herbivore_species_extinction,
                z6_max_flora_energy=self.config.z6_max_total_flora_energy,
                z7_max_total_herbivore_population=self.config.z7_max_total_herbivore_population,
                tick_metrics=tick_metrics,
            )
            if debug_summary:
                phase_timings_ms["termination"] = (time.perf_counter() - phase_started) * 1000.0

            self.tick += 1
            if debug_summary:
                self._log_debug_tick_summary(
                    latest_metrics=latest_metrics,
                    phase_timings_ms=phase_timings_ms,
                )

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
        self.start()
        logger.info("Simulation run loop entering background execution")

        while self.running and not self.terminated:
            tick_interval = 1.0 / max(0.1, self.config.tick_rate_hz)
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

        logger.info(
            "Simulation run loop exited (tick=%d, terminated=%s, reason=%s)",
            self.tick,
            self.terminated,
            self.termination_reason,
        )

    def update_tick_rate(self, tick_rate_hz: float) -> float:
        """Update live simulation tick speed while preserving safe lower bounds.

        Args:
            tick_rate_hz: Requested simulation ticks per second.

        Returns:
            Applied tick-rate value after clamping.
        """
        applied = max(0.1, float(tick_rate_hz))
        self.config.tick_rate_hz = applied
        logger.info("Simulation tick rate updated to %.2f Hz", applied)
        return applied

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
        # Wind can change snapshot content without advancing ticks.
        self._cached_snapshot_tick = -1
        self._cached_snapshot = None
        logger.info("Simulation wind updated to (vx=%.3f, vy=%.3f)", vx, vy)

    # ------------------------------------------------------------------
    # State snapshot for WebSocket streaming
    # ------------------------------------------------------------------

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return a serialisable snapshot of the current grid state.

        Returns:
            dict[str, Any]: Snapshot containing tick, termination state and
            environment dictionary (from :meth:`GridEnvironment.to_dict`).
        """
        if self._cached_snapshot_tick == self.tick and self._cached_snapshot is not None:
            return self._cached_snapshot

        snapshot = {
            "tick": self.tick,
            "terminated": self.terminated,
            "termination_reason": self.termination_reason,
            **self.env.to_dict(),
        }
        self._cached_snapshot_tick = self.tick
        self._cached_snapshot = snapshot
        return snapshot
