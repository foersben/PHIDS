def test_missing_triggers():
    from phids.api.ui_state.state.convert import from_sim_config
    from phids.api.ui_state.state import DraftState
    from phids.api.services.draft.trigger_rules import add_trigger_rule
    from phids.api.ui_state.state.convert import build_sim_config
    from phids.api.ui_state.substances import SubstanceDefinition

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=10, name="S10")]
    add_trigger_rule(
        draft,
        0,
        0,
        0,
        min_herbivore_population=5,
        activation_condition=None,
    )
    # The rule has action_type resource_withdrawal and substance_id -1 by default.
    draft.trigger_rules[0].substance_id = -1
    config = build_sim_config(draft)
    new_draft = from_sim_config(config)
