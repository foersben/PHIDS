import re

with open("src/phids/api/services/dse/task_manager.py", "r") as f:
    content = f.read()

# Replace TYPE_CHECKING, Any with TYPE_CHECKING
content = re.sub(r'from typing import TYPE_CHECKING, Any', 'from typing import TYPE_CHECKING', content)

# Replace asyncio.Task[Any] | None with asyncio.Task[None] | None
content = re.sub(r'asyncio\.Task\[Any\]', 'asyncio.Task[None]', content)

# Replace dict[str, Any] with dict[str, object]
content = re.sub(r'dict\[str, Any\]', 'dict[str, object]', content)

# Add from __future__ import annotations
content = content.replace('"""\n\nimport asyncio', '"""\n\nfrom __future__ import annotations\n\nimport asyncio')

with open("src/phids/api/services/dse/task_manager.py", "w") as f:
    f.write(content)
