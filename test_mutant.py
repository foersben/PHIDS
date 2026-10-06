from phids.engine.core.ecs import Entity
from phids.engine.components.plant import PlantComponent

def test_mutant():
    entity = Entity(100)
    # Removing a non-existent component should not raise an error
    # The default 'None' passed to pop() allows this.
    # The mutant removes the default 'None', which causes KeyError.
    try:
        entity.remove_component(PlantComponent)
        print("Test passed: no error on removing non-existent component.")
    except KeyError:
        print("Test failed: KeyError raised.")

test_mutant()
