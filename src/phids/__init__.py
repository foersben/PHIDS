"""Top-level package for PHIDS (Plant-Herbivore Interaction & Defense Simulator)."""

from phids.shared.logging_config import configure_logging

configure_logging()

__all__ = ["configure_logging"]
