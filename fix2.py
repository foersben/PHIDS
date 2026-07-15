with open('tests/integration/systems/test_interaction_hypothesis_pilot.py', 'r') as f:
    text = f.read()

text = text.replace('"phids.engine.systems.interaction._random_walk_step",', '"phids.engine.systems.interaction.movement._random_walk_step",')

with open('tests/integration/systems/test_interaction_hypothesis_pilot.py', 'w') as f:
    f.write(text)


with open('tests/integration/systems/test_interaction_property_invariants.py', 'r') as f:
    text2 = f.read()

text2 = text2.replace('"phids.engine.systems.interaction._random_walk_step",', '"phids.engine.systems.interaction.movement._random_walk_step",')

with open('tests/integration/systems/test_interaction_property_invariants.py', 'w') as f:
    f.write(text2)
