import os
import re

with open('/tmp/interaction_orig.py', 'r') as f:
    orig = f.read()

# Define the package directory
os.makedirs('src/phids/engine/systems/interaction', exist_ok=True)

# Helper to find function body easily
def extract_func(name, source):
    pattern = r'^def ' + name + r'\(.*?\n\)\s*->\s*[^:]+:.*?\n(?=^def |\Z)'
    match = re.search(pattern, source, flags=re.MULTILINE | re.DOTALL)
    if match:
        return match.group(0)

    # Handle single line definitions too
    pattern = r'^def ' + name + r'\(.*?:.*?\n(?=^def |\Z)'
    match = re.search(pattern, source, flags=re.MULTILINE | re.DOTALL)
    return match.group(0)
