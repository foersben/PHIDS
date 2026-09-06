"""Tests for triggers refactored packages."""
from unittest.mock import Mock

import numpy as np

from phids.api.schemas.triggers import (
    EnvironmentalSignalInitiator,
    HerbivoreAttackInitiator,
    ResourceWithdrawalAction,
    SynthesizeSubstanceAction,
)
from phids.engine.systems.signaling.triggers.actions import _apply_synthesize_action, _process_single_trigger_action
from phids.engine.systems.signaling.triggers.evaluation import (
    _evaluate_environmental_initiator_njit,
    _evaluate_environmental_signal,
    _evaluate_herbivore_initiator_njit,
    _evaluate_initiator,
)
from phids.engine.systems.signaling.triggers.phase import (
    _phase_evaluate_triggers,
    _process_compiled_trigger_for_species,
)


class PlantComponentMock:
    """Mock for PlantComponent."""

    def __init__(self, entity_id=1, species_id=1, x=1, y=1):
        """Init mock."""
        self.entity_id = entity_id
        self.species_id = species_id
        self.x = x
        self.y = y


class MockEnv:
    """Mock env."""

    def __init__(self):
        """Init env mock."""
        self.num_signals = 2
        self.signal_layers = np.array([[[0.0, 0.0], [0.0, 0.0]], [[0.0, 0.0], [0.0, 5.0]]])


def test_apply_synthesize_action_cov() -> None:
    """Test synthesis logic branching."""
    action = SynthesizeSubstanceAction(
        substance_id=1,
        is_toxin=True,
        synthesis_duration=10,
        lethal=True,
        lethality_rate=1.0,
        repellent=False,
        repellent_walk_ticks=0,
        aftereffect_ticks=5,
        energy_cost_per_tick=0.0,
        irreversible=False,
    )

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema
            self.activation_condition_dump = None

    trig = TriggerMock(Mock(action=action, aftereffect_ticks=5))
    plant = PlantComponentMock()
    world = Mock()
    world.create_entity.return_value = Mock(entity_id=2)
    owner_substance_by_key = {}
    substance_entities = []

    _apply_synthesize_action(trig, plant, world, owner_substance_by_key, substance_entities)  # type: ignore[arg-type]
    assert len(substance_entities) == 1

    owner_substance_by_key[(1, 1)].active = False
    owner_substance_by_key[(1, 1)].triggered_last_tick = False
    owner_substance_by_key[(1, 1)].synthesis_remaining = 0
    owner_substance_by_key[(1, 1)].aftereffect_remaining_ticks = 0

    _apply_synthesize_action(trig, plant, world, owner_substance_by_key, substance_entities)  # type: ignore[arg-type]
    assert owner_substance_by_key[(1, 1)].synthesis_remaining == 10

    owner_substance_by_key[(1, 1)].active = True
    owner_substance_by_key[(1, 1)].triggered_last_tick = True
    owner_substance_by_key[(1, 1)].synthesis_remaining = 1
    owner_substance_by_key[(1, 1)].aftereffect_remaining_ticks = 1

    _apply_synthesize_action(trig, plant, world, owner_substance_by_key, substance_entities)  # type: ignore[arg-type]
    assert owner_substance_by_key[(1, 1)].triggered_this_tick


def test_process_single_trigger_action_cov() -> None:
    """Test processing single action triggers."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema
            self.activation_condition_dump = None

    plant = PlantComponentMock()
    env = Mock()
    world = Mock()

    action1 = ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=10)
    trig1 = TriggerMock(Mock(action=action1, activation_condition=None))
    _process_single_trigger_action(trig1, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]
    assert plant.target_nutrition_factor == 0.5  # type: ignore[attr-defined]
    assert plant.withdrawal_ticks_remaining == 10  # type: ignore[attr-defined]

    action_unknown = Mock()
    trig2 = TriggerMock(Mock(action=action_unknown))
    _process_single_trigger_action(trig2, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]


def test_process_single_trigger_action_cov_2() -> None:
    """Test conditional checks for process_single_trigger_action."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema
            self.activation_condition_dump = Mock()

    plant = PlantComponentMock()
    env = Mock()
    world = Mock()

    action1 = ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=10)
    trig1 = TriggerMock(Mock(action=action1, activation_condition=Mock()))
    import phids.engine.systems.signaling.triggers.actions as actions

    actions._check_activation_condition = Mock(return_value=False)
    actions._process_single_trigger_action(trig1, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]

    actions._check_activation_condition = Mock(return_value=True)
    actions._process_single_trigger_action(trig1, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]
    assert plant.target_nutrition_factor == 0.5  # type: ignore[attr-defined]


def test_evaluate_environmental_signal_branches() -> None:
    """Test evaluate environmental signal branches."""
    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    init_hill = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="hill", min_concentration=0.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_hill, plant, env)
    assert res

    init_log = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="logarithmic", min_concentration=2.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_log, plant, env)
    assert res

    init_hill_f = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="hill", min_concentration=0.0, half_saturation=10.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_hill_f, plant, env)
    assert res

    init_step = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=6.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_step, plant, env)
    assert not res

    init_oob = EnvironmentalSignalInitiator(
        signal_id=99, response_curve="step", min_concentration=6.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_oob, plant, env)
    assert not res


def test_evaluate_environmental_signal_branches_2() -> None:
    """Test edge cases for evaluate environmental signal."""
    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)
    init_hill = EnvironmentalSignalInitiator(
        signal_id=0, response_curve="hill", min_concentration=0.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_hill, plant, env)
    assert not res

    init_unk = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=6.0, half_saturation=1.0, hill_cooperativity=1.0
    )
    init_unk.response_curve = "unknown"  # type: ignore[assignment]
    res = getattr(_evaluate_environmental_signal, "py_func", _evaluate_environmental_signal)(init_unk, plant, env)
    assert not res


def test_evaluate_initiator_branches() -> None:
    """Test initiator branches."""

    class CompiledTriggerMock:
        def __init__(self, schema):
            self.schema = schema

    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    init_env = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=2.0, half_saturation=1.0, hill_cooperativity=1.0
    )

    class FakeSchema:
        initiator = init_env

    trig = CompiledTriggerMock(FakeSchema())
    res = getattr(_evaluate_initiator, "py_func", _evaluate_initiator)(trig, plant, env, {})
    assert res

    class FakeInit:
        pass

    class FakeSchemaFalse:
        initiator = FakeInit()

    trig_false = CompiledTriggerMock(FakeSchemaFalse())
    res = getattr(_evaluate_initiator, "py_func", _evaluate_initiator)(trig_false, plant, env, {})
    assert not res


def test_evaluate_environmental_initiator_njit_branches() -> None:
    """Test NJIT signal environmental functions."""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    signal_layer = np.zeros((2, 2))
    signal_layer[0, 0] = 5.0
    signal_layer[1, 1] = 1.0

    out_mask = np.zeros(2, dtype=np.bool_)

    getattr(_evaluate_environmental_initiator_njit, "py_func", _evaluate_environmental_initiator_njit)(
        xs, ys, signal_layer, 0, 2.0, 0.0, 0.0, out_mask
    )
    assert out_mask[0]
    assert not out_mask[1]

    signal_layer[1, 1] = 0.0
    getattr(_evaluate_environmental_initiator_njit, "py_func", _evaluate_environmental_initiator_njit)(
        xs, ys, signal_layer, 1, 0.0, 2.0, 1.0, out_mask
    )
    assert out_mask[0]
    assert not out_mask[1]

    signal_layer[1, 1] = 1.0
    getattr(_evaluate_environmental_initiator_njit, "py_func", _evaluate_environmental_initiator_njit)(
        xs, ys, signal_layer, 2, 2.0, 0.0, 0.0, out_mask
    )
    assert out_mask[0]
    assert not out_mask[1]

    getattr(_evaluate_environmental_initiator_njit, "py_func", _evaluate_environmental_initiator_njit)(
        xs, ys, signal_layer, 99, 2.0, 0.0, 0.0, out_mask
    )
    assert not out_mask[0]


def test_evaluate_herbivore_initiator_njit_cov() -> None:
    """Test herbivore initiator check."""
    xs = np.array([0])
    ys = np.array([0])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 10

    out_mask = np.zeros(1, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(
        xs, ys, 1, 5, swarm_grid, out_mask
    )
    assert out_mask[0]


def test_process_compiled_trigger_for_species() -> None:
    """Test process compiled triggers."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema

    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    init_env = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=2.0, half_saturation=1.0, hill_cooperativity=1.0
    )

    class FakeSchema:
        initiator = init_env
        action = Mock(withdrawal_duration=10, apparent_nutrition_factor=1.0)

    trig = TriggerMock(FakeSchema())

    world = Mock()
    curve_map = {"step": 0}

    xs = np.array([1], dtype=np.int32)
    ys = np.array([1], dtype=np.int32)
    mask = np.zeros(1, dtype=np.bool_)

    _process_compiled_trigger_for_species(
        trig, [plant], xs, ys, mask, world, env, {}, {}, {}, [], curve_map, None  # type: ignore[arg-type]
    )

    init_herb = HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=1)

    class FakeSchemaHerb:
        initiator = init_herb
        action = Mock(withdrawal_duration=10, apparent_nutrition_factor=1.0)

    trig_herb = TriggerMock(FakeSchemaHerb())

    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[0, 1, 1] = 5
    mask = np.zeros(1, dtype=np.bool_)
    _process_compiled_trigger_for_species(
        trig_herb, [plant], xs, ys, mask, world, env, {}, {}, {}, [], curve_map, swarm_grid  # type: ignore[arg-type]
    )

    init_false = Mock()

    class FakeSchemaFalse:
        initiator = init_false
        action = Mock()

    trig_false = TriggerMock(FakeSchemaFalse())

    import phids.engine.systems.signaling.triggers.phase as phase

    phase._process_single_trigger = Mock()  # type: ignore[attr-defined]
    _process_compiled_trigger_for_species(
        trig_false, [plant], xs, ys, mask, world, env, {}, {}, {}, [], curve_map, None  # type: ignore[arg-type]
    )
    phase._process_single_trigger.assert_called_once()  # type: ignore[attr-defined]


def test_phase_evaluate_triggers() -> None:
    """Test evaluation logic triggers."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema

    init_env = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=2.0, half_saturation=1.0, hill_cooperativity=1.0
    )

    class FakeSchema:
        initiator = init_env
        action = Mock(withdrawal_duration=10, apparent_nutrition_factor=1.0)

    trig = TriggerMock(FakeSchema())

    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    class MockEntity:
        def get_component(self, _cls):
            return plant

    world = Mock()
    world.query.return_value = [MockEntity()]

    _phase_evaluate_triggers(world, env, {1: [trig]}, {}, Mock(get=lambda _k, _d: 0, _grid=None), {}, [])  # type: ignore[arg-type]


def test_phase_evaluate_triggers_no_plants() -> None:
    """Test triggers block with empty plants."""
    env = MockEnv()
    world = Mock()
    world.query.return_value = []

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema

    init_env = EnvironmentalSignalInitiator(
        signal_id=1, response_curve="step", min_concentration=2.0, half_saturation=1.0, hill_cooperativity=1.0
    )

    class FakeSchema:
        initiator = init_env
        action = Mock(withdrawal_duration=10, apparent_nutrition_factor=1.0)

    trig = TriggerMock(FakeSchema())

    _phase_evaluate_triggers(world, env, {1: [trig], 2: []}, {}, Mock(get=lambda _k, _d: 0, _grid=None), {}, [])  # type: ignore[arg-type]


def test_process_single_trigger_action_synthesize() -> None:
    """Test process synthesis action branch."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema
            self.activation_condition_dump = None

    plant = PlantComponentMock()
    env = Mock()
    world = Mock()
    world.create_entity.return_value = Mock(entity_id=2)

    action2 = SynthesizeSubstanceAction(
        substance_id=1,
        is_toxin=True,
        synthesis_duration=10,
        lethal=True,
        lethality_rate=1.0,
        repellent=False,
        repellent_walk_ticks=0,
        aftereffect_ticks=5,
        energy_cost_per_tick=0.0,
        irreversible=False,
    )
    trig2 = TriggerMock(Mock(action=action2, activation_condition=None, aftereffect_ticks=5))
    import phids.engine.systems.signaling.triggers.actions as actions

    actions._process_single_trigger_action(trig2, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]


def test_process_single_trigger() -> None:
    """Test single trigger dispatch."""

    class TriggerMock:
        def __init__(self, schema):
            self.schema = schema
            self.activation_condition_dump = None

    plant = PlantComponentMock()
    env = Mock()
    world = Mock()

    action1 = ResourceWithdrawalAction(apparent_nutrition_factor=0.5, withdrawal_duration=10)
    trig1 = TriggerMock(Mock(action=action1, activation_condition=None))

    import phids.engine.systems.signaling.triggers.actions as actions
    from phids.engine.systems.signaling.triggers.actions import _process_single_trigger

    actions._evaluate_initiator = Mock(return_value=False)  # type: ignore[attr-defined]
    _process_single_trigger(trig1, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]

    actions._evaluate_initiator = Mock(return_value=True)  # type: ignore[attr-defined]
    actions._process_single_trigger_action = Mock()  # type: ignore[attr-defined]
    _process_single_trigger(trig1, plant, world, env, {}, {}, {}, [])  # type: ignore[arg-type]
    actions._process_single_trigger_action.assert_called_once()  # type: ignore[attr-defined]

def test_evaluate_herbivore_initiator_njit_cov_2():
    xs = np.array([0])
    ys = np.array([0])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0

    out_mask = np.zeros(1, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert out_mask[0] == False

def test_evaluate_herbivore_initiator_njit_cov_2():
    """Test herbivore initiator cov 2."""
    xs = np.array([0])
    ys = np.array([0])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0

    out_mask = np.zeros(1, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert not out_mask[0]
def test_evaluate_herbivore_initiator_njit_cov_2():
    """Test herbivore initiator cov 2."""
    xs = np.array([0])
    ys = np.array([0])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0

    out_mask = np.zeros(1, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert not out_mask[0]
def test_evaluate_herbivore_initiator_njit_cov_2():
    """Test herbivore initiator cov 2."""
    xs = np.array([0])
    ys = np.array([0])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0

    out_mask = np.zeros(1, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert not out_mask[0]

def test_evaluate_herbivore_initiator_njit_cov_3():
    """Test herbivore initiator empty"""
    xs = np.array([], dtype=np.int32)
    ys = np.array([], dtype=np.int32)
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    out_mask = np.zeros(0, dtype=np.bool_)
    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert len(out_mask) == 0

def test_evaluate_herbivore_initiator_njit_cov_4():
    """Test herbivore initiator empty loop iteration branch"""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    out_mask = np.zeros(2, dtype=np.bool_)
    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert out_mask[0] == False
def test_evaluate_herbivore_initiator_njit_cov_5():
    """Test herbivore initiator when loop doesn't trigger True out_mask"""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    out_mask = np.zeros(2, dtype=np.bool_)
    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert not out_mask[0]
    assert not out_mask[1]

def test_evaluate_initiator_branches_false():
    class CompiledTriggerMock:
        def __init__(self, schema):
            self.schema = schema
    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    init_env = EnvironmentalSignalInitiator(signal_id=1, response_curve="step", min_concentration=6.0, half_saturation=1.0, hill_cooperativity=1.0)
    class FakeSchema:
        initiator = init_env
    trig = CompiledTriggerMock(FakeSchema())
    res = getattr(_evaluate_initiator, "py_func", _evaluate_initiator)(trig, plant, env, {})
    assert res == False
def test_evaluate_herbivore_initiator_njit_cov_6():
    """Test herbivore initiator when loop doesn't trigger True out_mask but has elements"""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0
    swarm_grid[1, 1, 1] = 0

    out_mask = np.zeros(2, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert out_mask[0] == False
    assert out_mask[1] == False

def test_evaluate_herbivore_initiator_njit_cov_7():
    """Test herbivore initiator when loop doesn't trigger True out_mask but has elements"""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 0
    swarm_grid[1, 1, 1] = 0

    out_mask = np.zeros(2, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)

    # Actually line 161 is out_mask[i] = pop >= min_population
    # This must be hit if the loop executes. Let's make sure we hit the False condition
    assert out_mask[0] == False
def test_evaluate_herbivore_initiator_njit_cov_8():
    """Test herbivore initiator when loop evaluates true"""
    xs = np.array([0, 1])
    ys = np.array([0, 1])
    swarm_grid = np.zeros((2, 2, 2), dtype=np.int32)
    swarm_grid[1, 0, 0] = 5
    swarm_grid[1, 1, 1] = 5

    out_mask = np.zeros(2, dtype=np.bool_)

    getattr(_evaluate_herbivore_initiator_njit, "py_func", _evaluate_herbivore_initiator_njit)(xs, ys, 1, 5, swarm_grid, out_mask)
    assert out_mask[0] == True
def test_evaluate_initiator_branches_herbivore():
    class CompiledTriggerMock:
        def __init__(self, schema):
            self.schema = schema

    env = MockEnv()
    plant = PlantComponentMock(entity_id=1, species_id=1, x=1, y=1)

    init_herb = HerbivoreAttackInitiator(herbivore_species_id=0, min_herbivore_population=1)
    class FakeSchemaHerb:
        initiator = init_herb
    trig_herb = CompiledTriggerMock(FakeSchemaHerb())

    pop_index = {(1, 1, 0): 5}
    res = getattr(_evaluate_initiator, "py_func", _evaluate_initiator)(trig_herb, plant, env, pop_index)
    assert res == True

    pop_index2 = {(1, 1, 0): 0}
    res = getattr(_evaluate_initiator, "py_func", _evaluate_initiator)(trig_herb, plant, env, pop_index2)
    assert res == False
