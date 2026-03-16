"""Input/output sub-package for scenario loading and deterministic replay serialisation.

This sub-package provides two I/O interfaces that bridge persisted configuration data and the
PHIDS runtime. The scenario module (``load_scenario_from_dict``, ``load_scenario_from_json``,
``scenario_to_json``) validates and deserialises ``SimulationConfig`` instances from JSON files
or Python mappings via Pydantic v2 model validation, enforcing all Rule-of-16 bounds and
reference-integrity constraints before any engine state is allocated. The replay module
(``ReplayBuffer``, ``serialise_state``, ``deserialise_state``) implements a compact binary frame
store using msgpack encoding, enabling length-prefixed per-tick state snapshots to be written to
disk and loaded for deterministic re-simulation or offline analysis.

Both interfaces are stateless with respect to the simulation runtime: they neither hold references
to live ``SimulationLoop`` instances nor mutate ECS world state, making them suitable for use in
batch worker processes and headless test environments.
"""
