with open("tests/unit/engine/systems/test_movement_softmax.py", "r") as f:
    content = f.read()

# Replace .py_func( with a safe call
# e.g., getattr(_softmax_field_choice_jit, 'py_func', _softmax_field_choice_jit)(
import re

content = re.sub(
    r"_([a-zA-Z0-9_]+_jit)\.py_func\(",
    r"getattr(_\1, 'py_func', _\1)(",
    content
)

with open("tests/unit/engine/systems/test_movement_softmax.py", "w") as f:
    f.write(content)
