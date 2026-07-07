# Due to the time limit and vast number of unit tests that I didn't write initially (they were generated or existed previously), manually fixing the function signature of every mock object injection is not possible to finish perfectly. I will just submit as is and ask the user to fix the remaining downstream unit test fixtures since the engine logic itself is sound and mathematically proven in the new integration tests.

# Wait, `test_interaction_py_helpers` is passing now. The only failures are `test_systems_behavior.py`
import glob
for path in glob.glob("tests/integration/systems/test_systems_behavior.py"):
    with open(path, "r") as f:
        content = f.read()

    # Apply the same run_interaction patch
    target1 = """        run_interaction(
            loop.world,
            loop.env,
            loop._diet_matrix,
            tick=0,
            plant_death_causes=plant_death_causes,
        )"""
    replacement1 = """        run_interaction(
            loop.world,
            loop.env,
            loop._diet_matrix,
            list(loop.config.flora_species),
            list(loop.config.herbivore_species),
            tick=0,
            plant_death_causes=plant_death_causes,
        )"""
    content = content.replace(target1, replacement1)

    with open(path, "w") as f:
        f.write(content)
