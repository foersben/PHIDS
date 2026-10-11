import re

with open("src/phids/api/ui_state/state/convert.py", "r") as f:
    content = f.read()

search_str = """if TYPE_CHECKING:
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.triggers import TriggerConditionSchema
    from phids.api.ui_state.substances import SubstanceDefinition"""

replace_str = """if TYPE_CHECKING:
    from phids.api.schemas.simulation import SimulationConfig
    from phids.api.schemas.triggers import TriggerConditionSchema, TriggerConfig
    from phids.api.ui_state.substances import SubstanceDefinition"""

if search_str in content:
    content = content.replace(search_str, replace_str)
    with open("src/phids/api/ui_state/state/convert.py", "w") as f:
        f.write(content)
    print("Patched top level imports!")
else:
    print("Could not find top level imports!")
