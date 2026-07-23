#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial
"""Rewrite all `from phids.api.schemas import ...` statements to use the new sub-package paths.

Symbol -> submodule mapping (no compatibility shim):
  base:       StrictBaseModel, SpeciesId, HerbivoreId, SubstanceId
  ecs:        PlantComponentSchema, SwarmComponentSchema, SubstanceComponentSchema
  conditions: HerbivorePresenceConditionSchema, SubstanceActiveConditionSchema,
              EnvironmentalSignalConditionSchema, AllOfConditionSchema,
              AnyOfConditionSchema, ConditionNode
  triggers:   SynthesizeSubstanceAction, ResourceWithdrawalAction, TriggerAction,
              TriggerConditionSchema, PassiveDefensesSchema
  species:    FloraSpeciesParams, HerbivoreSpeciesParams, HerbivoreResistancesSchema,
              DietCompatibilityMatrix
  placement:  InitialPlantPlacement, InitialSwarmPlacement, UniformPlacement,
              ClusteredPlacement, BandedPlacement, PlacementStrategy
  simulation: SimulationConfig
  responses:  SimulationStatusResponse, WindUpdatePayload, TickRateUpdatePayload,
              BatchJobState, BatchStartPayload
"""

from __future__ import annotations

import re
from pathlib import Path

SYMBOL_MAP: dict[str, str] = {
    # base
    "StrictBaseModel": "base",
    "SpeciesId": "base",
    "HerbivoreId": "base",
    "SubstanceId": "base",
    # ecs
    "PlantComponentSchema": "ecs",
    "SwarmComponentSchema": "ecs",
    "SubstanceComponentSchema": "ecs",
    # conditions
    "HerbivorePresenceConditionSchema": "conditions",
    "SubstanceActiveConditionSchema": "conditions",
    "EnvironmentalSignalConditionSchema": "conditions",
    "AllOfConditionSchema": "conditions",
    "AnyOfConditionSchema": "conditions",
    "ConditionNode": "conditions",
    # triggers
    "SynthesizeSubstanceAction": "triggers",
    "ResourceWithdrawalAction": "triggers",
    "TriggerAction": "triggers",
    "TriggerConditionSchema": "triggers",
    "PassiveDefensesSchema": "triggers",
    # species
    "FloraSpeciesParams": "species",
    "HerbivoreSpeciesParams": "species",
    "HerbivoreResistancesSchema": "species",
    "DietCompatibilityMatrix": "species",
    # placement
    "InitialPlantPlacement": "placement",
    "InitialSwarmPlacement": "placement",
    "UniformPlacement": "placement",
    "ClusteredPlacement": "placement",
    "BandedPlacement": "placement",
    "PlacementStrategy": "placement",
    # simulation
    "SimulationConfig": "simulation",
    # responses
    "SimulationStatusResponse": "responses",
    "WindUpdatePayload": "responses",
    "TickRateUpdatePayload": "responses",
    "BatchJobState": "responses",
    "BatchStartPayload": "responses",
}

# Pattern matches any `from phids.api.schemas import ...` block including multi-line ones.
IMPORT_PATTERN = re.compile(
    r"(?P<indent>[ \t]*)from phids\.api\.schemas import\s*(?:\(\s*)?(?P<symbols>[^)]+?)(?:\s*\))?(?=\n)",
    re.DOTALL,
)


def extract_symbols(raw: str) -> list[str]:
    """Clean a raw symbol string (possibly multi-line with backslash continuations)."""
    cleaned = raw.replace("\\\n", " ").replace("\n", " ").replace("(", "").replace(")", "")
    symbols = []
    for part in cleaned.split(","):
        sym = part.strip().rstrip(",")
        # Strip inline comments
        if "#" in sym:
            sym = sym[: sym.index("#")].strip()
        if sym:
            symbols.append(sym)
    return symbols


def build_replacements(symbols: list[str], indent: str) -> str:
    """Group symbols by submodule and emit one import line per submodule."""
    groups: dict[str, list[str]] = {}
    for sym in symbols:
        sub = SYMBOL_MAP.get(sym)
        if sub is None:
            raise ValueError(f"Unknown symbol in phids.api.schemas: '{sym}'. Add it to SYMBOL_MAP.")
        groups.setdefault(sub, []).append(sym)

    lines = []
    for sub in sorted(groups):
        syms = groups[sub]
        if len(syms) == 1:
            lines.append(f"{indent}from phids.api.schemas.{sub} import {syms[0]}")
        else:
            inner = f",\n{indent}    ".join(sorted(syms))
            lines.append(f"{indent}from phids.api.schemas.{sub} import (\n{indent}    {inner},\n{indent})")
    return "\n".join(lines)


def rewrite_file(path: Path) -> bool:
    """Return True if the file was modified."""
    text = path.read_text(encoding="utf-8")
    if "from phids.api.schemas import" not in text:
        return False

    # Parse ALL import blocks in the file (including lazy/local ones)
    # We handle multi-line imports with parentheses manually.
    out_lines: list[str] = []
    i = 0
    lines = text.splitlines(keepends=True)
    changed = False

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")
        indent_match = re.match(r"^(?P<indent>[ \t]*)from phids\.api\.schemas import", stripped)
        if indent_match:
            indent = indent_match.group("indent")
            # Collect the full import statement (may span multiple lines with parens or backslash)
            full = stripped
            j = i
            if "(" in full and ")" not in full:
                # Multi-line parenthesised import
                j += 1
                while j < len(lines) and ")" not in lines[j]:
                    full += " " + lines[j].strip()
                    j += 1
                if j < len(lines):
                    full += " " + lines[j].strip()
            elif full.endswith("\\"):
                # Backslash continuation
                full = full.rstrip("\\")
                j += 1
                while j < len(lines) and lines[j].rstrip("\n").endswith("\\"):
                    full += " " + lines[j].strip().rstrip("\\")
                    j += 1
                if j < len(lines):
                    full += " " + lines[j].strip()

            # Extract `import X, Y, Z` part
            sym_match = re.search(r"from phids\.api\.schemas import\s*\(?\s*(.+?)\s*\)?$", full, re.DOTALL)
            if sym_match:
                symbols = extract_symbols(sym_match.group(1))
                replacement = build_replacements(symbols, indent)
                out_lines.append(replacement + "\n")
                changed = True
            else:
                # Unexpected format - leave unchanged
                out_lines.append(line)
            i = j + 1
        else:
            out_lines.append(line)
            i += 1

    if changed:
        path.write_text("".join(out_lines), encoding="utf-8")
    return changed


def main() -> None:
    """Walk src/, tests/, and mutants/ and rewrite all old schema imports in-place."""
    roots = [Path("src"), Path("tests"), Path("mutants")]
    modified: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if rewrite_file(py_file):
                modified.append(py_file)

    if modified:
        print(f"Rewrote {len(modified)} file(s):")
        for p in sorted(modified):
            print(f"  {p}")
    else:
        print("No files required modification.")


if __name__ == "__main__":
    main()
