---
type: role
title: Directives
status: active
version: 0.1
description: "- **ECS Strictness:** Enforce ECS: Components MUST be raw NumPy arrays;\
  \ Systems contain all logic and operate on component arrays. Ban classes with..."
tags:
- phids
- ecs
- numba
- python
timestamp: "2026-07-21T16:01:38Z"
resources:
- flow_field.py
- src/phids/shared/constants.py
role: Engine Developer
---

# Directives
- **ECS Strictness:** Enforce ECS: Components MUST be raw NumPy arrays; Systems contain all logic and operate on component arrays. Ban classes with behavior/state inside engine core.
- **Numba JIT:** Compiling all hot-path numerical loops (`flow_field.py`) with `@njit`. Ban Python objects (`dict`, `list`, custom classes) inside JIT functions.
- **Rule of 16:** Enforce array capacity limits defined in `src/phids/shared/constants.py`.
- **Spatial Hashing:** Maintain spatial locality via `register_position`, `move_entity`, and `entities_at`.
- **Double Buffering:** Restrict engine tick reads to current layer; write exclusively to `_write` layer. Perform state swaps on tick completion.
