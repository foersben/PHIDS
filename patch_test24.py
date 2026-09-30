import sys

with open("tests/integration/api/test_api_builder_and_helpers/test_builder_helpers.py", "r") as f:
    content = f.read()

target = """def test_substance_name_helpers_draft_overrides() -> None:
    \"\"\"Verify substance naming helpers honor draft-provided override labels.\"\"\"
    api_main._set_simulation_substance_names()

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Alarm")]
    api_main._set_simulation_substance_names(draft=draft)
    assert api_main._sim_substance_names[0] == "Alarm"
"""

replacement = """def test_substance_name_helpers_draft_overrides() -> None:
    \"\"\"Verify substance naming helpers honor draft-provided override labels.\"\"\"
    config = _config_with_trigger()
    api_main._set_simulation_substance_names(config)

    draft = DraftState.default()
    draft.substance_definitions = [SubstanceDefinition(substance_id=0, name="Alarm")]
    api_main._set_simulation_substance_names(config, draft=draft)
    assert api_main._sim_substance_names[0] == "Alarm"
"""

content = content.replace(target, replacement)

with open("tests/integration/api/test_api_builder_and_helpers/test_builder_helpers.py", "w") as f:
    f.write(content)
