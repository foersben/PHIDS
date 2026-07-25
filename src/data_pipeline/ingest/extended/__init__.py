# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""PHIDS Extended Dataset Ingest Subpackage.

LEGAL NOTICE - READ BEFORE IMPORTING
=====================================
This subpackage contains ingest clients for ecological databases that carry
**Non-Commercial** (NC) or **No-Derivatives** (ND) license restrictions that
are INCOMPATIBLE with the PHIDS Proprietary Commercial License.

The databases integrated here are:

  - BIEN (Botanical Information and Ecology Network)
      License: CC-BY-NC-ND 4.0
      Restriction: Non-Commercial, No Derivatives. Data MUST NOT be
      bundled with or published as part of any commercial product.

  - LEDA Traitbase
      License: Academic Use Only (no open-data license granted).
      Restriction: Mass extraction or redistribution without written
      permission from the copyright holders is prohibited.

  - GIFT (Global Inventory of Floras and Traits)
      License: CC-BY-SA 4.0
      Restriction: Any derivative work MUST be distributed under the
      same CC-BY-SA license. This is incompatible with the Proprietary
      Commercial License.

TECHNICAL SAFEGUARDS
====================
This module WILL RAISE A RuntimeError at import time if the environment
variable ``PHIDS_EXTENDED_MODE`` is not explicitly set to ``"1"``.

This guard is intentional. It prevents any accidental import of these
clients into the default ``run_all.py`` pipeline, which would constitute
a license violation.

To use the extended pipeline, you must explicitly opt-in:

    PHIDS_EXTENDED_MODE=1 uv run --group pipeline python src/data_pipeline/run_extended.py

Or via Just:

    just etl-extended

CACHE ISOLATION
===============
All clients in this subpackage write to:

    src/data_pipeline/cache/extended/

This directory is tracked in ``.gitignore`` with an explicit warning
and MUST NEVER be committed to version control or uploaded to the
``foersben/PHIDS-empirical-database`` Hugging Face repository.

The compiled output of the extended pipeline is published ONLY to:

    foersben/PHIDS-extended-dataset (CC-BY-NC-SA 4.0)

"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Hard runtime guard: block accidental import
# ---------------------------------------------------------------------------

_EXTENDED_MODE_ENV = "PHIDS_EXTENDED_MODE"

if os.environ.get(_EXTENDED_MODE_ENV) != "1":
    raise RuntimeError(
        "\n"
        "=" * 70 + "\n"
        "LEGAL PROTECTION BLOCK: Extended dataset subpackage import blocked.\n"
        "=" * 70 + "\n"
        "\n"
        "You attempted to import from 'data_pipeline.ingest.extended' without\n"
        "setting the required opt-in environment variable.\n"
        "\n"
        "This is a deliberate safety guard. The databases in this subpackage\n"
        "carry Non-Commercial (NC) or No-Derivatives (ND) license restrictions\n"
        "that are INCOMPATIBLE with the PHIDS Proprietary Commercial License.\n"
        "\n"
        "To opt-in and accept the NC license obligations, set:\n"
        "\n"
        "    export PHIDS_EXTENDED_MODE=1\n"
        "\n"
        "Then re-run using the dedicated extended pipeline:\n"
        "\n"
        "    just etl-extended\n"
        "\n"
        "DO NOT set this variable in the default ETL pipeline (run_all.py).\n"
        "DO NOT commit the resulting cache files.\n"
        "DO NOT publish extended data to foersben/PHIDS-empirical-database.\n"
        "=" * 70
    )

# Expose the set of NC source names for provenance validation
NC_SOURCES: frozenset[str] = frozenset({"BIEN", "LEDA", "GIFT"})

__all__ = ["NC_SOURCES"]
