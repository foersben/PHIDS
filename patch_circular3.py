with open("src/phids/engine/systems/signaling/helpers/evaluation.py", "r") as f:
    content = f.read()

content = content.replace("from phids.engine.systems.signaling.triggers import _evaluate_environmental_initiator_njit, _evaluate_herbivore_initiator_njit, _process_single_trigger, _process_single_trigger_action\n\n\ndef _evaluate_single_trigger_for_species(", "def _evaluate_single_trigger_for_species(")


new_helper = """def _evaluate_single_trigger_for_species(
    trig: CompiledTrigger,
    plants: list[PlantComponent],
    xs: npt.NDArray[np.int32],
    ys: npt.NDArray[np.int32],
    mask: npt.NDArray[np.bool_],
    world: ECSWorld,
    env: GridEnvironment,
    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],
    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],
    swarm_grid: npt.NDArray[np.int32] | None,
    curve_map: dict[str, int],
    active_substance_ids_by_owner: dict[int, set[int]],
    substance_entities: list[Entity],
) -> None:
    from phids.engine.systems.signaling.triggers import _evaluate_environmental_initiator_njit, _evaluate_herbivore_initiator_njit, _process_single_trigger, _process_single_trigger_action"""


content = content.replace("def _evaluate_single_trigger_for_species(\n    trig: CompiledTrigger,\n    plants: list[PlantComponent],\n    xs: npt.NDArray[np.int32],\n    ys: npt.NDArray[np.int32],\n    mask: npt.NDArray[np.bool_],\n    world: ECSWorld,\n    env: GridEnvironment,\n    owner_substance_by_key: dict[tuple[int, int], SubstanceComponent],\n    swarm_population_by_cell_species: SwarmPopulationIndex | dict[tuple[int, int, int], int],\n    swarm_grid: npt.NDArray[np.int32] | None,\n    curve_map: dict[str, int],\n    active_substance_ids_by_owner: dict[int, set[int]],\n    substance_entities: list[Entity],\n) -> None:", new_helper)

with open("src/phids/engine/systems/signaling/helpers/evaluation.py", "w") as f:
    f.write(content)
