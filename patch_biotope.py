import re

with open('src/phids/engine/core/biotope.py', 'r') as f:
    content = f.read()

content = content.replace(
    'return val_y0 * (1.0 - dy) + val_y1 * dy',
    'return float(val_y0 * (1.0 - dy) + val_y1 * dy)'
)

content = content.replace(
    'return v',
    'return float(v)'
)

with open('src/phids/engine/core/biotope.py', 'w') as f:
    f.write(content)
