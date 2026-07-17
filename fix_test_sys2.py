import re
with open("tests/integration/systems/test_systems_behavior.py", "r") as f:
    content = f.read()

content = content.replace("from phids.api.schemas import HerbivoreSpeciesParams", "from phids.api.schemas import HerbivoreSpeciesParams\n    from phids.api.schemas import FloraSpeciesParams")

with open("tests/integration/systems/test_systems_behavior.py", "w") as f:
    f.write(content)
