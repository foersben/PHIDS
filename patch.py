with open('tests/unit/engine/systems/test_movement_softmax.py', 'r') as f:
    content = f.read()

content = content.replace('_softmax_field_choice_jit.py_func', "getattr(_softmax_field_choice_jit, 'py_func', _softmax_field_choice_jit)")
content = content.replace('_flat_field_choice_jit.py_func', "getattr(_flat_field_choice_jit, 'py_func', _flat_field_choice_jit)")
content = content.replace('_weighted_field_choice_jit.py_func', "getattr(_weighted_field_choice_jit, 'py_func', _weighted_field_choice_jit)")
content = content.replace('_choose_neighbour_by_flow_probability_jit.py_func', "getattr(_choose_neighbour_by_flow_probability_jit, 'py_func', _choose_neighbour_by_flow_probability_jit)")
content = content.replace('_random_walk_step_jit.py_func', "getattr(_random_walk_step_jit, 'py_func', _random_walk_step_jit)")

with open('tests/unit/engine/systems/test_movement_softmax.py', 'w') as f:
    f.write(content)
