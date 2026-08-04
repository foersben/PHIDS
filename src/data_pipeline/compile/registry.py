"""Registry for hardcoded substance and VOC mappings."""
from __future__ import annotations

_SUBSTANCE_REGISTRY: dict[str, int] = {
    "alpha-pinene": 0,
    "beta-caryophyllene": 1,
    "(Z)-3-hexenyl acetate": 2,
    "methyl salicylate": 3,
    "linalool": 4,
    "indole": 5,
    "(E)-beta-farnesene": 6,
    "taxine": 10,
    "atropine": 11,
    "hyoscine": 12,
    "coniine": 13,
    "colchicine": 14,
    "aconitine": 15,
    "veratrine": 16,
    "protoanemonin": 17,
    "solanine": 18,
    "digitoxin": 19,
    "digoxin": 20,
    "amygdalin": 21,
    "linamarin": 22,
    "dhurrin": 23,
    "tannic acid": 30,
    "gallotannin": 31,
    "ellagitannin": 32,
}

_VOC_IDS: set[int] = {0, 1, 2, 3, 4, 5, 6}
