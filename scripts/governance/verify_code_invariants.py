#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""AST and Lexical Code Invariants Verifier for PHIDS.

Enforces:
1. Lexical checks: Prohibition of unapproved bypass comments (# noqa, # type: ignore, etc.).
2. Systems AST checks: Zero stateful OOP classes inside 'src/phids/engine/systems/' (pure functions only).
3. JIT AST checks: Zero dynamic allocations (ast.List, ast.Dict, ast.Set, comprehensions) inside @njit kernels.
4. Arity AST checks: Parameter arity <= 4 for public non-JIT functions in 'src/phids/'.
5. Ratchet baseline: Compares findings against a baseline snapshot to prevent regressions.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT_DIR / "scripts" / "governance" / "code_invariants_baseline.json"

BYPASS_TOKENS = {
    "# noqa",
    "# type: ignore",
    "# complexipy: ignore",
    "# pragma: no cover",
}


@dataclass(frozen=True, slots=True)
class InvariantViolation:
    """Represents a code invariant violation."""

    file_path: str
    line_number: int
    rule_id: str
    message: str

    @property
    def key(self) -> str:
        """Deterministic fingerprint for baseline comparison."""
        return f"{self.file_path}::{self.rule_id}::{self.message}"


def check_lexical_bypasses(file_path: Path) -> list[InvariantViolation]:
    """Scan tokens in file for bypass comments."""
    violations: list[InvariantViolation] = []
    rel_path = str(file_path.relative_to(ROOT_DIR))
    try:
        with file_path.open("rb") as f:
            tokens = tokenize.tokenize(f.readline)
            for tok in tokens:
                if tok.type == tokenize.COMMENT:
                    comment_text = tok.string.strip()
                    for bypass in BYPASS_TOKENS:
                        if bypass in comment_text:
                            violations.append(
                                InvariantViolation(
                                    file_path=rel_path,
                                    line_number=tok.start[0],
                                    rule_id="NI-01-BYPASS",
                                    message=f"Bypass comment: '{comment_text}'",
                                )
                            )
    except Exception as e:
        violations.append(
            InvariantViolation(
                file_path=rel_path,
                line_number=1,
                rule_id="PARSER-ERROR",
                message=f"Tokenize failed: {e}",
            )
        )
    return violations


def _is_dataclass(decorator_list: list[ast.expr]) -> bool:
    """Return True if class has dataclass decorator."""
    for d in decorator_list:
        if isinstance(d, ast.Name) and d.id == "dataclass":
            return True
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass":
            return True
    return False


def _is_typed_dict(bases: list[ast.expr]) -> bool:
    """Return True if class inherits from TypedDict or NamedTuple."""
    return any(isinstance(base, ast.Name) and base.id in ("TypedDict", "NamedTuple") for base in bases)


def _get_mutating_methods(body: list[ast.stmt]) -> list[str]:
    """Return names of instance methods in class body."""
    methods: list[str] = []
    for item in body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name not in ("__init__", "__post_init__"):
                methods.append(item.name)
    return methods


def _is_jit_decorated(decorator_list: list[ast.expr]) -> bool:
    """Return True if function has JIT compilation decorator."""
    for d in decorator_list:
        if isinstance(d, ast.Name) and d.id in ("njit", "jit"):
            return True
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in ("njit", "jit"):
            return True
    return False


def _compute_effective_arity(args: ast.arguments) -> int:
    """Compute positional arity excluding self or cls."""
    pos_args = len(args.args) + len(args.posonlyargs)
    if args.args and args.args[0].arg in ("self", "cls"):
        pos_args -= 1
    return pos_args


class CodeInvariantsVisitor(ast.NodeVisitor):
    """AST visitor enforcing structural domain invariants."""

    def __init__(self, file_path: Path) -> None:
        """Initialize visitor for given file."""
        self.file_path = file_path
        self.rel_path = str(file_path.relative_to(ROOT_DIR))
        self.is_systems = "src/phids/engine/systems" in self.rel_path
        self.is_engine = "src/phids/engine" in self.rel_path
        self.violations: list[InvariantViolation] = []
        self._inside_jit = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check for stateful OOP classes in engine systems."""
        if self.is_systems and not _is_dataclass(node.decorator_list) and not _is_typed_dict(node.bases):
            methods = _get_mutating_methods(node.body)
            if methods:
                self.violations.append(
                    InvariantViolation(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        rule_id="NI-06-OOP",
                        message=f"Stateful class '{node.name}' with methods {methods} in engine systems",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Flag dynamic reflection via getattr or hasattr in engine code."""
        if self.is_engine and isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr"):
            self.violations.append(
                InvariantViolation(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    rule_id="NI-06-REFLECTION",
                    message=f"Dynamic reflection '{node.func.id}' prohibited in engine. Use typed fields or protocols.",
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check function arity and track JIT compilation status."""
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check async function arity."""
        self._check_function(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        is_jit = _is_jit_decorated(node.decorator_list)

        # Arity check for public functions outside numerical kernels
        if not is_jit and not node.name.startswith("_"):
            pos_args = _compute_effective_arity(node.args)
            if pos_args > 4:
                self.violations.append(
                    InvariantViolation(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        rule_id="NI-06-ARITY",
                        message=f"Public function '{node.name}' arity {pos_args} exceeds threshold 4",
                    )
                )

        prev_jit = self._inside_jit
        if is_jit:
            self._inside_jit = True
        self.generic_visit(node)
        self._inside_jit = prev_jit

    def visit_List(self, node: ast.List) -> None:
        """Flag list creation inside JIT."""
        if self._inside_jit:
            self.violations.append(
                InvariantViolation(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    rule_id="NI-06-ALLOC",
                    message="Dynamic ast.List allocation inside @njit kernel",
                )
            )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        """Flag dict creation inside JIT."""
        if self._inside_jit:
            self.violations.append(
                InvariantViolation(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    rule_id="NI-06-ALLOC",
                    message="Dynamic ast.Dict allocation inside @njit kernel",
                )
            )
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set) -> None:
        """Flag set creation inside JIT."""
        if self._inside_jit:
            self.violations.append(
                InvariantViolation(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    rule_id="NI-06-ALLOC",
                    message="Dynamic ast.Set allocation inside @njit kernel",
                )
            )
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Flag list comprehension inside JIT."""
        if self._inside_jit:
            self.violations.append(
                InvariantViolation(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    rule_id="NI-06-ALLOC",
                    message="Dynamic ast.ListComp comprehension inside @njit kernel",
                )
            )
        self.generic_visit(node)


def audit_file(file_path: Path) -> list[InvariantViolation]:
    """Run lexical and AST audit on a single Python file."""
    violations = check_lexical_bypasses(file_path)
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        visitor = CodeInvariantsVisitor(file_path)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    except Exception as e:
        violations.append(
            InvariantViolation(
                file_path=str(file_path.relative_to(ROOT_DIR)),
                line_number=1,
                rule_id="PARSER-ERROR",
                message=f"AST parse failed: {e}",
            )
        )
    return violations


def audit_repository(target_dir: Path) -> list[InvariantViolation]:
    """Audit all Python source files in the target directory."""
    all_violations: list[InvariantViolation] = []
    for py_file in sorted(target_dir.rglob("*.py")):
        # Skip virtualenvs and caches
        if any(part in py_file.parts for part in (".venv", ".git", "__pycache__", ".cache")):
            continue
        all_violations.extend(audit_file(py_file))
    return all_violations


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="PHIDS Code Invariants Auditor & Ratchet.")
    parser.add_argument(
        "--target",
        type=Path,
        default=ROOT_DIR / "src" / "phids",
        help="Target directory to audit (defaults to 'src/phids').",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Path to the baseline snapshot JSON file.",
    )
    parser.add_argument(
        "--snapshot-create",
        action="store_true",
        help="Record current violations into baseline snapshot to establish ratchet.",
    )
    args = parser.parse_args()

    print(f"🔍 Auditing code invariants across '{args.target.relative_to(ROOT_DIR)}'...")
    violations = audit_repository(args.target)

    if args.snapshot_create:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        snapshot_data = [asdict(v) for v in violations]
        with args.baseline.open("w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2)
        print(f"📸 Baseline snapshot written to '{args.baseline.relative_to(ROOT_DIR)}' ({len(violations)} items).")
        return 0

    # Verification against baseline
    baseline_keys: set[str] = set()
    if args.baseline.exists():
        with args.baseline.open("r", encoding="utf-8") as f:
            raw_data: list[dict[str, Any]] = json.load(f)
            baseline_keys = {f"{item['file_path']}::{item['rule_id']}::{item['message']}" for item in raw_data}

    new_violations: list[InvariantViolation] = []
    for v in violations:
        if v.key not in baseline_keys:
            new_violations.append(v)

    if new_violations:
        print(f"\n❌ Found {len(new_violations)} NEW code invariant violation(s):")
        for v in new_violations:
            print(f"  • [{v.rule_id}] {v.file_path}:{v.line_number} - {v.message}")
        print("\n💥 Build rejected: Invariant regressions detected. Fix violations or update baseline.")
        return 1

    print(
        f"✅ Invariants verified. Total monitored: {len(violations)}, "
        f"Baseline exceptions: {len(baseline_keys)}, New violations: 0."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
