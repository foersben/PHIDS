import re

file_path = "tests/integration/api/test_ui_routes.py"
with open(file_path, "r") as f:
    code = f.read()

# Fix test_flow_field_helpers_compute_gradient_and_apply_camouflage
code = code.replace(
    'flow_field._compute_flow_field_impl(\n            np.array([[1e-6]], dtype=np.float64),\n            np.array([[1.0]], dtype=np.float64),\n            np.array([[0.0]], dtype=np.float64),\n            1,\n            1,\n            np.zeros((1, 1), dtype=np.float64),\n            np.zeros((1, 1), dtype=np.float64),\n            np.zeros((1, 1), dtype=np.float64),\n            1.0,\n            1.0,\n            0.6,\n            1e-4,\n        )[0, 0]',
    'flow_field._compute_flow_field_impl(\n            np.array([[1e-6]], dtype=np.float64),\n            np.array([[1.0]], dtype=np.float64),\n            np.array([[[0.0]]], dtype=np.float64),\n            1,\n            1,\n            np.zeros((1, 1), dtype=np.float64),\n            np.zeros((1, 1), dtype=np.float64),\n            np.zeros((1, 1), dtype=np.float64),\n            1.0,\n            1.0,\n            0.6,\n            1e-4,\n        )[0, 0]'
)

with open(file_path, "w") as f:
    f.write(code)
