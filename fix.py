import re

with open('src/phids/engine/systems/interaction/metabolism.py', 'r') as f:
    meta = f.read()
meta = meta.replace('from phids.engine.systems.interaction.population import _accumulate_tile_population\n', 'from phids.engine.systems.interaction.population import _accumulate_tile_population\nfrom phids.engine.systems.interaction.movement import _random_walk_step\nfrom phids.engine.components.swarm import SwarmComponent\n')
meta = meta.replace('    from phids.engine.components.swarm import SwarmComponent\n', '')
with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(meta)

with open('src/phids/engine/systems/interaction/movement.py', 'r') as f:
    mov = f.read()
mov = mov.replace('from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population\n', 'from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population\nfrom phids.engine.components.plant import PlantComponent\n')
with open('src/phids/engine/systems/interaction/movement.py', 'w') as f:
    f.write(mov)
