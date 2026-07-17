import re
with open("tests/integration/systems/test_systems_behavior.py", "r") as f:
    content = f.read()

# I need to fix the duplicate resistances argument in test_systems_behavior.py
content = re.sub(r'resistances=HerbivoreResistancesSchema\(\),\n\s*resistances=\{\},', r'resistances={},', content)
content = re.sub(r'resistances=\{\},\n\s*resistances=\{\},', r'resistances={},', content)
content = re.sub(r'resistances=\{\},\s*resistances=\{\},', r'resistances={},', content)

# But wait, what does it exactly look like now?
