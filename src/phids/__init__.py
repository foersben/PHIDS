"""
PHIDS (Plant-Herbivore Interaction & Defense Simulator) top-level package.

This package serves as the canonical entry point for the PHIDS ecosystem simulation engine,
orchestrating the initialization of logging and exposing core engine modules. The architectural
design adheres to a rigorous data-oriented paradigm, facilitating deterministic simulation of
plant-herbivore interactions, systemic acquired resistance, and metabolic attrition within a
spatially hashed, double-buffered environment. By centralizing configuration and module exposure,
this package ensures reproducibility and scientific integrity across all simulation phases, from
flow-field computation to telemetry export. The package's structure is intentionally minimal,
reflecting its role as a foundational layer for both API and UI surfaces, and its compliance with
the Rule of 16 and O(1) spatial hash invariants.
"""

from phids.shared.logging_config import configure_logging

configure_logging()

__all__ = ["configure_logging"]
