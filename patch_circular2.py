import re

with open("src/phids/engine/systems/signaling/helpers/evaluation.py", "r") as f:
    content = f.read()

content = content.replace("from phids.engine.systems.signaling.triggers import (\n    _evaluate_environmental_initiator_njit,\n    _evaluate_herbivore_initiator_njit,\n    _process_single_trigger,\n    _process_single_trigger_action,\n)", "")

with open("src/phids/engine/systems/signaling/helpers/evaluation.py", "w") as f:
    f.write(content)
