with open('/tmp/interaction_orig.py', 'r') as f:
    text = f.read()

import re
match = re.search(r'(def _resolve_swarm_metabolism_and_reproduction\(.*?\n\)\s*->\s*bool:.*?return True)', text, re.DOTALL | re.MULTILINE)

with open('src/phids/engine/systems/interaction/metabolism.py', 'r') as f:
    meta = f.read()

meta = re.sub(
    r'def _resolve_swarm_metabolism_and_reproduction\(.*?\n\)\s*->\s*bool:.*?\n    return True\n',
    match.group(1) + '\n',
    meta,
    flags=re.DOTALL | re.MULTILINE
)

with open('src/phids/engine/systems/interaction/metabolism.py', 'w') as f:
    f.write(meta)
