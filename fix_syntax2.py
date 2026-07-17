import re
with open("tests/integration/systems/test_systems_behavior.py", "r") as f:
    content = f.read()

content = content.replace("HerbivoreSpeciesParams(resistances={}, ", "HerbivoreSpeciesParams(")
content = content.replace("resistances={},\n            resistances={},", "resistances={},")

with open("tests/integration/systems/test_systems_behavior.py", "w") as f:
    f.write(content)
