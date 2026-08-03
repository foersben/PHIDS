# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Integration tests for the headless Monte Carlo batch runner.

This package decomposes batch runner testing into three focused modules:

- ``test_headless_runner``: Per-run headless execution path, tick sequencing,
  early termination, and delegate forwarding.
- ``test_aggregation``: Statistical aggregation of multi-run ensembles, including
  mean/std computation, extinction probability, padding, and per-species breakdowns.
- ``test_batch_orchestration``: End-to-end ``BatchRunner.execute_batch`` path with
  mixed future outcomes, JSON sanitization, and strict output validation.

Because ``_run_single_headless`` invokes Numba JIT on first call, all tests use
minimal grid dimensions (4x4) and short tick counts (3-5) to keep wall-clock time
acceptable in CI. The ``ProcessPoolExecutor`` path is not exercised directly;
instead, fakes are injected via monkeypatch for isolation.
"""
