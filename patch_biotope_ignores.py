with open('src/phids/engine/core/biotope.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "advected_scratch[x, y] = _advect_cell(" in line:
        lines[i] = line.rstrip() + "  # type: ignore\n"
    elif "v = _convolve_cell(" in line:
        lines[i] = line.rstrip() + "  # type: ignore\n"
    elif "v *= decay" in line:
        lines[i] = line.rstrip() + "  # type: ignore\n"
    elif "if v < epsilon:" in line:
        lines[i] = line.rstrip() + "  # type: ignore\n"
    elif "v = 0.0" in line and "if v < epsilon:" in lines[i-1]:
        lines[i] = line.rstrip() + "  # type: ignore\n"
    elif "write_buffer[x, y] = v" in line:
        lines[i] = line.rstrip() + "  # type: ignore\n"

with open('src/phids/engine/core/biotope.py', 'w') as f:
    f.writelines(lines)
