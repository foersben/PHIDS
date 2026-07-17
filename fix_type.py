import os
import re

with open("src/phids/api/routers/config/herbivores.py", "r") as f:
    content = f.read()

content = content.replace('resistances_updates: dict[str, float] = pp.resistances.copy()', 'resistances_updates: dict[str, float] = pp.resistances.copy()')

content = content.replace('updates["resistances"] = pp.resistances.model_copy(update=resistances_updates)', 'updates["resistances"] = resistances_updates')

content = content.replace('if resistances_updates:', 'if resistances_updates != pp.resistances:')

with open("src/phids/api/routers/config/herbivores.py", "w") as f:
    f.write(content)
