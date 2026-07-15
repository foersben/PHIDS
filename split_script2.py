import re
import os

with open('/tmp/interaction_orig.py', 'r') as f:
    orig = f.read()

# I will just write a python script to parse the ast or manually split it.
import ast
tree = ast.parse(orig)

def get_node_source(node, source):
    lines = source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    return '\n'.join(lines[start:end])

funcs = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        funcs[node.name] = get_node_source(node, orig)

print(list(funcs.keys()))
