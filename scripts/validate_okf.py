#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
"""Forwarder shim redirecting to scripts/governance/validate_okf.py."""

import runpy
from pathlib import Path
from typing import Any

_TARGET = Path(__file__).resolve().parent / "governance" / "validate_okf.py"


def __getattr__(name: str) -> Any:
    """Dynamically delegate attribute lookups to scripts.governance.validate_okf."""
    from scripts.governance import validate_okf

    return getattr(validate_okf, name)


if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
