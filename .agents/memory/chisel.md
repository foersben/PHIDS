---
type: Agent Role
sources:
  - resource: src/phids/engine/systems/signaling/triggers/phase.py
---
## 2026-10-24 - Preserving Architectural Documentation in Refactoring
Learning: When splitting a monolithic file (like `triggers.py`) into smaller, modular sub-packages, it is easy to accidentally delete critical module-level architectural docstrings (e.g. details on why imports are structured a certain way to avoid Python global dictionary lookups).
Action: Always ensure that multi-paragraph architectural docstrings from the top of the original module are preserved by carefully relocating them to the new package's `__init__.py` or the most relevant submodule. Also, do not commit throwaway scripts used for patching files.
