"""API sub-package implementing the dual HTTP/WebSocket interface surface for PHIDS.

This sub-package assembles the complete operator-facing runtime control surface for the PHIDS
simulation engine. The composition root (``phids.api.main``) owns the singleton live
``SimulationLoop``, application middleware, and shared Jinja2 template environment, while transport
loop orchestration for WebSocket streams is delegated to ``phids.api.websockets`` manager classes.
Route logic is partitioned across five dedicated router modules: ``config`` for draft-state builder
mutations, ``simulation`` for scenario loading and lifecycle control, ``telemetry`` for observation
and export, ``batch`` for Monte Carlo ensemble execution, and ``ui`` for server-rendered HTMX
partial responses. The schema module (``phids.api.schemas``) defines all Pydantic v2 ingress models
and species-parameter dataclasses; the ``ui_state`` module (``phids.api.ui_state``) maintains the
server-side draft accumulator that separates editable configuration from the live simulation. The
presenter, service, and websocket sub-packages further isolate payload assembly, mutation
orchestration, and stream transport concerns from HTTP route declarations, implementing a clean
draft-versus-live architectural boundary.

All Pydantic validation is performed at the API ingress boundary, after which the engine operates
on trusted internal state structures consistent with the Rule-of-16 allocation constraints and the
double-buffered environmental semantics of ``GridEnvironment``.
"""
