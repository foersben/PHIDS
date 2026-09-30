import re

with open("src/phids/api/schemas/triggers.py", "r") as f:
    content = f.read()

# I see it in `_map_legacy_trigger_fields`, maybe that broke it? Let me replace dict[str, Any] with dict[str, object] there to see if that works.
content = re.sub(r'dict\[str, Any\]', 'dict[str, object]', content)
content = re.sub(r'from typing import Annotated, Any, Literal', 'from typing import Annotated, Literal', content)

with open("src/phids/api/schemas/triggers.py", "w") as f:
    f.write(content)
