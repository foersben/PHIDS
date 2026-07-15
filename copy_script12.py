import re
with open('/tmp/interaction_orig.py', 'r') as f:
    orig = f.read()

match = re.search(r'(def _perform_mitosis\(.*?\n\)\s*->\s*SwarmComponent:.*?\n(?=^def |\Z))', orig, re.DOTALL | re.MULTILINE)
mitosis = match.group(1)

match2 = re.search(r'(def _resolve_swarm_metabolism_and_reproduction\(.*?\n\)\s*->\s*bool:.*?\n(?=^def |\Z))', orig, re.DOTALL | re.MULTILINE)
meta = match2.group(1)

text = f"""# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

\"\"\"Metabolism, reproduction, and mitosis logic for swarms in the interaction system.\"\"\"

from __future__ import annotations

from typing import TYPE_CHECKING

from phids.engine.components.swarm import SwarmComponent
from phids.engine.systems.interaction.movement import _random_walk_step
from phids.engine.systems.interaction.population import _accumulate_tile_population

if TYPE_CHECKING:
    from phids.engine.core.biotope import GridEnvironment
    from phids.engine.core.ecs import ECSWorld, Entity


{mitosis}

{meta}
"""

with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(text)
