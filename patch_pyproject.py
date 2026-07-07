import re
with open("pyproject.toml", "r") as f:
    content = f.read()

target = """[tool.mutmut]
paths_to_mutate = "src/phids/engine/systems/,src/phids/engine/core/"
"""
replacement = """[tool.mutmut]
source_paths = "src/phids/engine/core/flow_field.py"
"""
content = content.replace(target, replacement)
with open("pyproject.toml", "w") as f:
    f.write(content)

with open("setup.cfg", "w") as f:
    f.write("""[mutmut]
source_paths=src/phids/engine/core/flow_field.py
""")
