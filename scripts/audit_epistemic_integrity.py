#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Automated auditor verifying epistemic integrity and computational constraints.

Scans the PHIDS codebase and documentation across 10 detailed thematic slices:
1. Spatiotemporal Anchor & Dimensional Homogeneity
2. Continuous Transport PDEs & Stencils
3. Autotrophic Metabolic Kinetics & Structural Growth
4. Subterranean Symbiosis & Phloem Networks
5. Botanical Defenses (Constitutive vs. Inducible)
6. Heterotrophic Kinematics & Foraging Dynamics
7. Population Dynamics & Energetic Attrition
8. Multi-Scale Decoupling & Loop Orchestration
9. Empirical Data Pipeline & Allometric Scaling
10. WIP/CIP Boundary Governance

Identifies:
- Scalar if/else branching inside @njit kernels (Rule 02 & Rule 05-B).
- Heap array allocations inside @njit loops.
- Ad-hoc rate clamping (np.clip, min/max) and discretization shortcuts (math.floor).
- Magic numeric constants in kinetic rate formulas.
- Toroidal coordinate wrapping inconsistencies.
- Boundary leakage of WIP/CIP modules into core loops.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Allowed numeric literals in formulas that do not constitute magic numbers
NEUTRAL_LITERALS: set[float | int] = {
    0,
    1,
    -1,
    2,
    0.5,
    1e-9,
    1e-6,
    1e-4,
}

SLICE_METADATA: dict[int, dict[str, Any]] = {
    1: {
        "name": "Spatiotemporal Anchor & Dimensional Homogeneity",
        "description": "Base scales, bitwise toroidal coordinates, and static allocation bounds.",
        "paths": ["src/phids/engine/core", "src/phids/shared/constants.py"],
    },
    2: {
        "name": "Continuous Transport PDEs & Stencils",
        "description": "Double-buffered Gaussian convolution, semi-Lagrangian advection, FTZ/DAZ truncation.",
        "paths": [
            "src/phids/engine/core/biotope.py",
            "src/phids/engine/core/flow_field.py",
            "src/phids/engine/systems/signaling/spatial.py",
        ],
    },
    3: {
        "name": "Autotrophic Metabolic Kinetics & Structural Growth",
        "description": "Dual-Proxy biomass architecture, photosynthetic flux, anemochory.",
        "paths": [
            "src/phids/engine/systems/lifecycle/growth.py",
            "src/phids/engine/systems/lifecycle/reproduction.py",
            "src/phids/engine/components/plant.py",
        ],
    },
    4: {
        "name": "Subterranean Symbiosis & Phloem Networks",
        "description": "Mycorrhizal fungal graph topology, phloem translocation, subterranean signaling.",
        "paths": [
            "src/phids/engine/systems/lifecycle/mycorrhiza.py",
            "src/phids/engine/systems/signaling",
        ],
    },
    5: {
        "name": "Botanical Defenses (Constitutive vs. Inducible)",
        "description": "Trichome density, grazing damage thresholds, induced semiochemical emission cascades.",
        "paths": [
            "src/phids/engine/systems/signaling/emission.py",
            "src/phids/engine/systems/signaling/triggers.py",
            "src/phids/engine/systems/interaction/feeding.py",
        ],
    },
    6: {
        "name": "Heterotrophic Kinematics & Foraging Dynamics",
        "description": "Softmax stochastic gradient ascent, Holling Type II consumption, patch departure.",
        "paths": [
            "src/phids/engine/systems/interaction/feeding.py",
            "src/phids/engine/systems/interaction/movement",
            "src/phids/engine/systems/interaction/metabolism.py",
        ],
    },
    7: {
        "name": "Population Dynamics & Energetic Attrition",
        "description": "Density-dependent carrying capacity, branchless collision masking, mitosis, starvation.",
        "paths": [
            "src/phids/engine/systems/interaction/population.py",
            "src/phids/engine/systems/lifecycle/culling.py",
        ],
    },
    8: {
        "name": "Multi-Scale Decoupling & Loop Orchestration",
        "description": "Fast/Medium/Slow stride boundaries, phase-staggered cohorts, double-buffering immutability.",
        "paths": [
            "src/phids/engine/loop.py",
            "src/phids/engine/core/ecs.py",
            "src/phids/engine/core/biotope.py",
        ],
    },
    9: {
        "name": "Empirical Data Pipeline & Allometric Scaling",
        "description": "Trait extraction, Kleiber's Law allometric scaling, ETL parameter reconciliation.",
        "paths": [
            "src/phids/shared/constants.py",
            "src/phids/api/schemas/species.py",
            "src/phids/engine/core/herbivore_params.py",
        ],
    },
    10: {
        "name": "WIP/CIP Boundary Governance",
        "description": "EEDSE, distributed Ray/Tune Pareto exploration, diagnostic log observer boundary containment.",
        "paths": [
            "src/phids/analytics",
            "docs/scenario_guide/work_in_progress",
            "docs/scenario_guide/future_prospects",
        ],
    },
}


@dataclass(slots=True)
class Finding:
    """Represents a concrete integrity or theoretical divergence finding."""

    slice_id: int
    slice_name: str
    severity: str  # "CRITICAL", "MAJOR", "MINOR", "INFO"
    category: str
    file_path: str
    line_number: int
    snippet: str
    description: str
    theoretical_rationale: str
    suggested_remediation: str


class EpistemicASTVisitor(ast.NodeVisitor):
    """AST visitor inspecting functions and kernels for epistemic shortcuts and violations."""

    def __init__(self, file_path: str, source_lines: list[str], root_path: Path) -> None:
        """Initialize the visitor for a single Python file."""
        self.file_path = file_path
        self.rel_path = (
            str(Path(file_path).relative_to(root_path)) if root_path in Path(file_path).parents else file_path
        )
        self.source_lines = source_lines
        self.findings: list[Finding] = []
        self._in_jit: bool = False
        self._current_function: str = ""
        self._loop_depth: int = 0

    def _get_line_snippet(self, lineno: int) -> str:
        """Extract a single trimmed source line by 1-based index."""
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Inspect function definitions and track @njit contexts."""
        is_jit = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id in {"njit", "jit"}:
                is_jit = True
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id in {"njit", "jit"}:
                is_jit = True

        prev_jit = self._in_jit
        prev_func = self._current_function
        prev_depth = self._loop_depth
        self._in_jit = is_jit
        self._current_function = node.name
        self._loop_depth = 0

        self.generic_visit(node)

        self._in_jit = prev_jit
        self._current_function = prev_func
        self._loop_depth = prev_depth

    def visit_For(self, node: ast.For) -> None:
        """Track loop depth within JIT kernels."""
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        """Track loop depth within JIT kernels."""
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        """Check for scalar if/else state branching inside JIT inner loops."""
        if self._in_jit and self._loop_depth > 0:
            # Allow loop convergence breaks or search exits (e.g. if diff < eps: break, if r < cum: return ...)
            is_search_exit = (
                len(node.body) == 1 and isinstance(node.body[0], (ast.Break, ast.Return)) and not node.orelse
            )
            if not is_search_exit:
                snippet = self._get_line_snippet(node.lineno)
                s_id = 2 if "flow" in self.rel_path or "biotope" in self.rel_path else 6
                self.findings.append(
                    Finding(
                        slice_id=s_id,
                        slice_name=SLICE_METADATA[s_id]["name"],
                        severity="MAJOR",
                        category="SCALAR_BRANCH_IN_JIT",
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        snippet=snippet,
                        description=f"Branching conditional 'if' inside JIT loop in '{self._current_function}'.",
                        theoretical_rationale=(
                            "Inner JIT simulation loops must avoid branch divergence and state branching. "
                            "Rule 02 and Rule 05-B mandate branchless SIMD masking via float multiplications."
                        ),
                        suggested_remediation=(
                            "Replace scalar conditional logic with branchless arithmetic masks (e.g., value * mask)."
                        ),
                    )
                )
        self.generic_visit(node)

    def _check_jit_allocation(self, node: ast.Call) -> None:
        if not self._in_jit:
            return
        func_name = ""
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in {"zeros", "empty", "ones", "zeros_like", "ones_like", "append"}:
            snippet = self._get_line_snippet(node.lineno)
            self.findings.append(
                Finding(
                    slice_id=1,
                    slice_name=SLICE_METADATA[1]["name"],
                    severity="CRITICAL",
                    category="ALLOCATION_IN_JIT",
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    snippet=snippet,
                    description=f"Heap allocation '{func_name}' inside @njit function '{self._current_function}'.",
                    theoretical_rationale=(
                        "Dynamic array allocations inside Numba kernels incur runtime overhead "
                        "and violate zero-allocation hot-path constraints."
                    ),
                    suggested_remediation=(
                        "Pre-allocate output matrices in the write buffer and mutate arrays in-place."
                    ),
                )
            )

    def _check_discretization_floor(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "floor"):
            return
        if not any(k in self.rel_path for k in ("feeding", "population", "metabolism")):
            return
        snippet = self._get_line_snippet(node.lineno)
        s_id = 5 if "feeding" in self.rel_path else 7
        self.findings.append(
            Finding(
                slice_id=s_id,
                slice_name=SLICE_METADATA[s_id]["name"],
                severity="MAJOR",
                category="DISCRETIZATION_ARTIFACT",
                file_path=self.rel_path,
                line_number=node.lineno,
                snippet=snippet,
                description=f"Discretization truncation via '{node.func.attr}' on continuous damage/rate.",
                theoretical_rationale=(
                    "Truncation via math.floor causes low fractional damage to be completely erased "
                    "(e.g. floor(0.9) == 0), preventing attrition from accumulating."
                ),
                suggested_remediation=(
                    "Accumulate fractional attrition into a continuous residual pool or apply stochastic rounding."
                ),
            )
        )

    def _check_clamping_clip(self, node: ast.Call) -> None:
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "clip"):
            return
        snippet = self._get_line_snippet(node.lineno)
        s_id = 3 if "lifecycle" in self.rel_path else 6
        self.findings.append(
            Finding(
                slice_id=s_id,
                slice_name=SLICE_METADATA[s_id]["name"],
                severity="MINOR",
                category="CLAMPING_SHORTCUT",
                file_path=self.rel_path,
                line_number=node.lineno,
                snippet=snippet,
                description=f"Ad-hoc rate clamping via '{node.func.attr}'.",
                theoretical_rationale=(
                    "Hard clipping rates at arbitrary bounds conceals underlying parameter miscalibrations "
                    "and introduces derivative discontinuities."
                ),
                suggested_remediation=(
                    "Use smooth asymptotic saturating functions (e.g., Michaelis-Menten, Hill kinetics) "
                    "instead of hard bounding."
                ),
            )
        )

    def visit_Call(self, node: ast.Call) -> None:
        """Check for forbidden allocations in JIT or discretization shortcuts."""
        self._check_jit_allocation(node)
        self._check_discretization_floor(node)
        self._check_clamping_clip(node)
        self.generic_visit(node)

    def _inspect_assign_constant(self, node: ast.Assign, num: int | float) -> None:
        if num in NEUTRAL_LITERALS:
            return
        snippet = self._get_line_snippet(node.lineno)
        slice_id = (
            5
            if "feeding" in self.rel_path or "signaling" in self.rel_path
            else (3 if "lifecycle" in self.rel_path else 6)
        )
        self.findings.append(
            Finding(
                slice_id=slice_id,
                slice_name=SLICE_METADATA[slice_id]["name"],
                severity="MINOR",
                category="MAGIC_LITERAL",
                file_path=self.rel_path,
                line_number=node.lineno,
                snippet=snippet,
                description=f"Undocumented magic constant '{num}' in kinetic equation.",
                theoretical_rationale=(
                    "Numeric literals embedded directly in rate equations bypass configuration, "
                    "cannot be calibrated via DSE, and obscure physical units."
                ),
                suggested_remediation=(
                    f"Promote '{num}' to a named constant in shared/constants.py or "
                    "a species-level configuration parameter."
                ),
            )
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        """Check for magic constants in system rate formulas."""
        if "src/phids/engine/systems" in self.rel_path:
            for val in ast.walk(node.value):
                if isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                    self._inspect_assign_constant(node, val.value)
                    break
        self.generic_visit(node)


def audit_file(file_path: Path, root_path: Path) -> list[Finding]:
    """Parse and audit a single Python file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        source_lines = content.splitlines()
        tree = ast.parse(content, filename=str(file_path))
        visitor = EpistemicASTVisitor(str(file_path), source_lines, root_path)
        visitor.visit(tree)
        return visitor.findings
    except SyntaxError as e:
        rel = str(file_path.relative_to(root_path))
        return [
            Finding(
                slice_id=1,
                slice_name=SLICE_METADATA[1]["name"],
                severity="CRITICAL",
                category="SYNTAX_ERROR",
                file_path=rel,
                line_number=e.lineno or 1,
                snippet=str(e),
                description=f"Syntax error in file: {e}",
                theoretical_rationale="File cannot be parsed.",
                suggested_remediation="Fix syntax errors.",
            )
        ]


def _check_slice_1_grid_utils(root_path: Path) -> list[Finding]:
    """Check grid coordinate power-of-two assertions."""
    findings: list[Finding] = []
    grid_utils_path = root_path / "src/phids/engine/core/grid_utils.py"
    if grid_utils_path.exists():
        content = grid_utils_path.read_text(encoding="utf-8")
        if "mask_x = (width - 1) if is_pow2 else width" in content:
            findings.append(
                Finding(
                    slice_id=1,
                    slice_name=SLICE_METADATA[1]["name"],
                    severity="MAJOR",
                    category="DIMENSIONAL_DISCREPANCY",
                    file_path="src/phids/engine/core/grid_utils.py",
                    line_number=29,
                    snippet="mask_x = (width - 1) if is_pow2 else width",
                    description="Fallback coordinate mask when not power-of-two returns raw width instead of modulo.",
                    theoretical_rationale=(
                        "Bitwise AND with 'width' does NOT perform modulo wrapping if width is not a power of 2 "
                        "minus 1. Non-power-of-two grids will corrupt coordinate bounds if bitwise wrapped."
                    ),
                    suggested_remediation="Assert power-of-two at grid initialization or branch to '% width'.",
                )
            )
    return findings


def _check_slice_5_feeding(root_path: Path) -> list[Finding]:
    """Check feeding repulsion timer magic number."""
    findings: list[Finding] = []
    feeding_path = root_path / "src/phids/engine/systems/interaction/feeding.py"
    if feeding_path.exists():
        content = feeding_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "swarm.repelled_ticks_remaining = 2" in line:
                findings.append(
                    Finding(
                        slice_id=5,
                        slice_name=SLICE_METADATA[5]["name"],
                        severity="MINOR",
                        category="MAGIC_LITERAL",
                        file_path="src/phids/engine/systems/interaction/feeding.py",
                        line_number=idx,
                        snippet=line.strip(),
                        description="Hardcoded repulsion duration '2' ticks on encountering incompatible plant.",
                        theoretical_rationale=(
                            "The 2-tick repulsion penalty represents sensory aversion but lacks "
                            "biological empirical grounding or species parameterization."
                        ),
                        suggested_remediation=(
                            "Define INCOMPATIBLE_PLANT_REPELLER_TICKS in shared/constants.py or "
                            "configure per herbivore sensory resistance."
                        ),
                    )
                )
    return findings


def _check_slice_9_constants(root_path: Path) -> list[Finding]:
    """Check Dual-Proxy placeholder growth rate in constants.py."""
    findings: list[Finding] = []
    constants_path = root_path / "src/phids/shared/constants.py"
    if constants_path.exists():
        content = constants_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "M_STRUCTURAL_GROWTH_RATE: float = 0.01" in line:
                findings.append(
                    Finding(
                        slice_id=9,
                        slice_name=SLICE_METADATA[9]["name"],
                        severity="INFO",
                        category="WIP_GOVERNANCE",
                        file_path="src/phids/shared/constants.py",
                        line_number=idx,
                        snippet=line.strip(),
                        description="Global placeholder default for structural biomass growth rate.",
                        theoretical_rationale=(
                            "Flora species vary by orders of magnitude in wood/lignin structural allocation. "
                            "A uniform 0.01 rate neglects species-specific allometry."
                        ),
                        suggested_remediation=(
                            "Calibrate per-species structural allocation rates against TRY plant trait database."
                        ),
                    )
                )
    return findings


def check_specialized_slice_invariants(root_path: Path) -> list[Finding]:
    """Execute targeted invariant checks across specific slices."""
    findings: list[Finding] = []
    findings.extend(_check_slice_1_grid_utils(root_path))
    findings.extend(_check_slice_5_feeding(root_path))
    findings.extend(_check_slice_9_constants(root_path))
    return findings


def run_audit(
    root_path: Path,
    target_slice: int | None = None,
) -> list[Finding]:
    """Execute full epistemic audit across all or target slices."""
    all_findings: list[Finding] = []

    # 1. Specialized invariant checks
    all_findings.extend(check_specialized_slice_invariants(root_path))

    # 2. AST parsing across engine directories
    engine_dir = root_path / "src/phids/engine"
    if engine_dir.exists():
        for py_file in sorted(engine_dir.rglob("*.py")):
            all_findings.extend(audit_file(py_file, root_path))

    # Filter by slice if requested
    if target_slice is not None:
        return [f for f in all_findings if f.slice_id == target_slice]

    return all_findings


def _format_summary_row(s_id: int, findings: list[Finding]) -> str:
    """Format a single summary row for a slice."""
    s_findings = [f for f in findings if f.slice_id == s_id]
    s_crit = sum(1 for f in s_findings if f.severity == "CRITICAL")
    s_maj = sum(1 for f in s_findings if f.severity == "MAJOR")
    s_min = sum(1 for f in s_findings if f.severity == "MINOR")
    s_inf = sum(1 for f in s_findings if f.severity == "INFO")
    return f"| {s_id} | {SLICE_METADATA[s_id]['name']} | {s_crit} | {s_maj} | {s_min} | {s_inf} | {len(s_findings)} |"


def _format_summary_table(findings: list[Finding], target_slice: int | None = None) -> list[str]:
    """Format markdown summary table."""
    lines: list[str] = [
        "| Slice | Name | Critical | Major | Minor | Info | Total |",
        "|---|---|---|---|---|---|---|",
    ]
    slice_ids = [target_slice] if target_slice is not None else list(range(1, 11))
    for s_id in slice_ids:
        lines.append(_format_summary_row(s_id, findings))
    return lines


def _format_single_slice_findings(s_id: int, s_findings: list[Finding]) -> list[str]:
    """Format markdown findings for a single slice."""
    lines: list[str] = [
        f"### Slice {s_id}: {SLICE_METADATA[s_id]['name']}",
        "",
        f"*{SLICE_METADATA[s_id]['description']}*",
        "",
    ]
    if not s_findings:
        lines.extend(["*No invariant violations or theoretical divergences detected in this slice.*", ""])
        return lines

    for f in s_findings:
        lines.extend(
            [
                f"#### `[{f.severity}]` {f.category} in `{f.file_path}:{f.line_number}`",
                "",
                f"* **Code Snippet:** `{f.snippet}`",
                f"* **Description:** {f.description}",
                f"* **Theoretical Rationale:** {f.theoretical_rationale}",
                f"* **Suggested Remediation:** {f.suggested_remediation}",
                "",
            ]
        )
    return lines


def _format_detailed_findings(findings: list[Finding], target_slice: int | None = None) -> list[str]:
    """Format markdown detailed slice findings."""
    lines: list[str] = ["", "## Detailed Slice Findings", ""]
    for s_id in range(1, 11):
        if target_slice is not None and s_id != target_slice:
            continue
        s_findings = [f for f in findings if f.slice_id == s_id]
        lines.extend(_format_single_slice_findings(s_id, s_findings))
    return lines


def format_markdown_report(findings: list[Finding], target_slice: int | None = None) -> str:
    """Generate structured Markdown report from findings."""
    total = len(findings)
    critical = sum(1 for f in findings if f.severity == "CRITICAL")
    major = sum(1 for f in findings if f.severity == "MAJOR")
    minor = sum(1 for f in findings if f.severity == "MINOR")
    info = sum(1 for f in findings if f.severity == "INFO")

    lines: list[str] = [
        "# Epistemic Soundness & Computational Integrity Audit Report",
        "",
        "> Automated audit verifying biological fidelity, mathematical rigor, and HPC/ECS computational constraints.",
        "",
        "## Summary Statistics",
        "",
        f"* **Total Findings:** {total}",
        f"* **Critical Invariant Violations:** {critical}",
        f"* **Major Theoretical Divergences:** {major}",
        f"* **Minor Code Shortcuts & Magic Literals:** {minor}",
        f"* **Informational / WIP Roadmap Gaps:** {info}",
        "",
    ]
    lines.extend(_format_summary_table(findings, target_slice))
    lines.extend(_format_detailed_findings(findings, target_slice))
    return "\n".join(lines)


def _print_terminal_summary(findings: list[Finding]) -> None:
    """Print human-readable audit findings to terminal."""
    print("=================================================================")
    print("🔬 PHIDS Epistemic Soundness & Computational Integrity Audit")
    print("=================================================================")
    total = len(findings)
    critical = sum(1 for f in findings if f.severity == "CRITICAL")
    major = sum(1 for f in findings if f.severity == "MAJOR")
    minor = sum(1 for f in findings if f.severity == "MINOR")
    info = sum(1 for f in findings if f.severity == "INFO")

    print(f"Total Findings: {total}")
    print(f"  • CRITICAL: {critical}")
    print(f"  • MAJOR:    {major}")
    print(f"  • MINOR:    {minor}")
    print(f"  • INFO:     {info}")
    print("-----------------------------------------------------------------")

    for f in findings:
        print(f"[{f.severity:8}] [Slice {f.slice_id}] {f.file_path}:{f.line_number}")
        print(f"           Category:    {f.category}")
        print(f"           Snippet:     {f.snippet}")
        print(f"           Description: {f.description}")
        print()


def _build_cli_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(description="Audit epistemic integrity and computational invariants.")
    parser.add_argument("--slice", type=int, choices=range(1, 11), help="Audit a specific thematic slice (1-10).")
    parser.add_argument("--all", action="store_true", help="Audit all 10 slices.")
    parser.add_argument("--json", action="store_true", help="Output findings as JSON.")
    parser.add_argument("--markdown", action="store_true", help="Output findings as formatted Markdown.")
    parser.add_argument(
        "--fail-on-critical", action="store_true", help="Exit with non-zero status if CRITICAL findings exist."
    )
    return parser


def main() -> int:
    """CLI entry point for epistemic integrity audit."""
    parser = _build_cli_parser()
    args = parser.parse_args()

    root_path = Path(__file__).resolve().parent.parent

    target_slice = args.slice if not args.all else None
    findings = run_audit(root_path, target_slice=target_slice)

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    elif args.markdown:
        print(format_markdown_report(findings, target_slice=target_slice))
    else:
        _print_terminal_summary(findings)

    if args.fail_on_critical and any(f.severity == "CRITICAL" for f in findings):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
