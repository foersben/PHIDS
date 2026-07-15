import re
import os
import ast

with open('/tmp/interaction_orig.py', 'r') as f:
    orig = f.read()

tree = ast.parse(orig)

def get_node_source(node, source):
    # This also grabs the decorators and docstrings properly
    lines = source.splitlines()
    # Find start line including decorators
    start = getattr(node, "decorator_list", [])
    if start:
        start_line = start[0].lineno - 1
    else:
        start_line = node.lineno - 1
    end_line = node.end_lineno
    return '\n'.join(lines[start_line:end_line])

funcs = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        funcs[node.name] = get_node_source(node, orig)


POPULATION = """# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Population utilities for interaction system.\"\"\"

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent

if TYPE_CHECKING:
    from phids.engine.core.ecs import ECSWorld

TILE_CARRYING_CAPACITY = 500

{accumulate}

{colocated}
"""

MOVEMENT = """# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Movement and pathfinding logic for swarms in the interaction system.\"\"\"

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from numba import njit

from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY, _accumulate_tile_population

if TYPE_CHECKING:
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

_orig_choice = random.choice
_orig_choices = random.choices

{gather_neighbours_jit}

{flat_field_choice_jit}

{weighted_field_choice_jit}

{choose_neighbour_by_flow_probability_jit}

{choose_neighbour_by_flow_probability}

{random_walk_step_jit}

{random_walk_step}

{python_flat_field_choice}

{python_weighted_field_choice}

{choose_neighbour_by_flow_probability_python}

{is_swarm_anchored}

{resolve_swarm_movement}
"""

FEEDING = """# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Herbivory logic for swarms feeding on flora in the interaction system.\"\"\"

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from phids.engine.components.plant import PlantComponent
from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld

{feed_on_single_plant}

{resolve_swarm_feeding}
"""

METABOLISM = """# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Metabolism, reproduction, and mitosis logic for swarms in the interaction system.\"\"\"

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    from phids.engine.components.swarm import SwarmComponent
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity

{perform_mitosis}

{resolve_swarm_metabolism_and_reproduction}
"""

INIT = """# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Interaction system: swarm gradient navigation, herbivory, metabolic attrition, and mitosis.

This module implements the second of three ordered per-tick simulation phases in the PHIDS engine.
The interaction phase resolves all herbivore-flora encounters after plant lifecycle dynamics have
been committed to the energy layers, but before chemical-defense substances are emitted and
diffused. This ordering is a deliberate architectural invariant: herbivory must operate against
the most current plant-energy state produced by the lifecycle phase, while the chemical-signaling
phase must be free to observe the post-herbivory energy landscape when computing diffusion
gradients and systemic acquired resistance signals. Toxin effects on swarm navigation are
therefore mediated indirectly through the flow-field gradient rather than through direct
component access, maintaining strict separation between signal propagation and entity mechanics.

Swarm movement is governed by probabilistic sampling over the 4-connected Von-Neumann
neighbourhood, weighted by the scalar flow-field gradient encoded in ``GridEnvironment.flow_field``.
When the local gradient range falls below the numerical threshold of 1x10^-6 - indicating a
chemically flat or saturated zone - movement inertia encoded in ``SwarmComponent.last_dx`` /
``SwarmComponent.last_dy`` introduces a directional persistence bias, approximating the
klinokinetic orientation behaviour observed in real arthropod foragers navigating low-stimulus
environments. Tile carrying capacity (``TILE_CARRYING_CAPACITY``) imposes a local density ceiling
analogous to interference competition: swarms occupying a cell whose aggregate population exceeds
the ceiling enter a transient random-walk dispersal phase, modelling the habitat
saturation-driven emigration documented in colonial insect foragers. Herbivory is applied
exclusively to stationary swarms (those that did not relocate during the current tick) via O(1)
spatial hash lookups; a species-pair diet-compatibility matrix gates energy transfer between each
herbivore-flora combination, ensuring phylogenetic dietary specificity. Metabolic attrition
deducts per-individual upkeep energy each tick; energy deficits are resolved as population
casualties computed by ⌈deficit / energy_min⌉, converting energetic debt directly into
individual mortality. Surplus energy above the swarm-baseline threshold is converted into new
individuals at cost ``energy_min * reproduction_energy_divisor``, implementing a simple
net-assimilation model of reproduction. Mitosis splits an oversized swarm into two equal halves
and registers both entities in the ECS world and spatial hash, mimicking the colony fission
events characteristic of social hymenoptera and clonal plant-grazer aggregations.

Attributes:
    TILE_CARRYING_CAPACITY: Maximum aggregate individual count permitted on a single grid cell
        before crowding-induced dispersal is triggered. Acts as an upper bound on local population
        density, preventing simulation degeneracy under unconstrained growth.

\"\"\"

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.feeding import _resolve_swarm_feeding
from phids.engine.systems.interaction.metabolism import _resolve_swarm_metabolism_and_reproduction
from phids.engine.systems.interaction.movement import _resolve_swarm_movement
from phids.engine.systems.interaction.population import _accumulate_tile_population
from phids.engine.systems.interaction.population import TILE_CARRYING_CAPACITY as TILE_CARRYING_CAPACITY
from phids.engine.systems.interaction.population import _co_located_swarm_population as _co_located_swarm_population

if TYPE_CHECKING:
    from phids.api.schemas import FloraSpeciesParams, HerbivoreSpeciesParams
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld

{run_interaction}
"""

with open('src/phids/engine/systems/interaction/population.py', 'w') as f:
    f.write(POPULATION.format(accumulate=funcs['_accumulate_tile_population'], colocated=funcs['_co_located_swarm_population']))

with open('src/phids/engine/systems/interaction/movement.py', 'w') as f:
    f.write(MOVEMENT.format(
        gather_neighbours_jit=funcs['_gather_neighbours_jit'],
        flat_field_choice_jit=funcs['_flat_field_choice_jit'],
        weighted_field_choice_jit=funcs['_weighted_field_choice_jit'],
        choose_neighbour_by_flow_probability_jit=funcs['_choose_neighbour_by_flow_probability_jit'],
        choose_neighbour_by_flow_probability=funcs['_choose_neighbour_by_flow_probability'],
        random_walk_step_jit=funcs['_random_walk_step_jit'],
        random_walk_step=funcs['_random_walk_step'],
        python_flat_field_choice=funcs['_python_flat_field_choice'],
        python_weighted_field_choice=funcs['_python_weighted_field_choice'],
        choose_neighbour_by_flow_probability_python=funcs['_choose_neighbour_by_flow_probability_python'],
        is_swarm_anchored=funcs['_is_swarm_anchored'],
        resolve_swarm_movement=funcs['_resolve_swarm_movement']
    ))

with open('src/phids/engine/systems/interaction/feeding.py', 'w') as f:
    f.write(FEEDING.format(feed_on_single_plant=funcs['_feed_on_single_plant'], resolve_swarm_feeding=funcs['_resolve_swarm_feeding']))

with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(METABOLISM.format(perform_mitosis=funcs['_perform_mitosis'], resolve_swarm_metabolism_and_reproduction=funcs['_resolve_swarm_metabolism_and_reproduction']))

with open('src/phids/engine/systems/interaction/__init__.py', 'w') as f:
    f.write(INIT.format(run_interaction=funcs['run_interaction']))
