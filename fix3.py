import ast

with open('src/phids/engine/systems/interaction/metabolism.py', 'r') as f:
    text = f.read()

tree = ast.parse(text)
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == '_perform_mitosis':
        print(ast.dump(node, indent=4))
