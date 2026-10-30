#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
"""Forwarder shim redirecting to scripts/simulation/phids_request_trace.py."""

import runpy
from pathlib import Path

_TARGET = Path(__file__).resolve().parent / "simulation" / "phids_request_trace.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
