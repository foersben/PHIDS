with open('tests/integration/systems/test_interaction_property_invariants.py', 'r') as f:
    text = f.read()

text = text.replace('"phids.engine.systems.interaction.movement._random_walk_step",', '"phids.engine.systems.interaction.movement._random_walk_step",')

with open('tests/integration/systems/test_interaction_property_invariants.py', 'w') as f:
    f.write(text)
