import re
with open(".agents/memory/canon.md", "r") as f:
    content = f.read()

content = "---\ntype: concept\ntitle: Canon Memory\nstatus: active\nversion: 1.0\ndescription: Memory for Canon.\n---\n\n" + content

with open(".agents/memory/canon.md", "w") as f:
    f.write(content)
