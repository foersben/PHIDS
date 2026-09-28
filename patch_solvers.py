import re

file_path = "src/phids/engine/core/flow/solvers.py"
with open(file_path, "r") as f:
    content = f.read()

search_block = """            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val
            diff = val - current[x, y]
            if diff > max_diff:
                max_diff = diff
            elif -diff > max_diff:
                max_diff = -diff"""

replace_block = """            val = base[x, y] + (decay * neighbours_sum * 0.25)
            nxt[x, y] = val
            diff = val - current[x, y]
            if diff < 0.0:
                diff = -diff
            max_diff = max(max_diff, diff)"""

new_content = content.replace(search_block, replace_block)
if new_content != content:
    with open(file_path, "w") as f:
        f.write(new_content)
    print("Patched solvers.py correctly.")
else:
    print("Could not patch solvers.py.")
