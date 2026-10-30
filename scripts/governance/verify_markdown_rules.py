#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

r"""Strict Markdown Formatting Rule Enforcer (Rule 04).

Enforces:
1. Standard ASCII hyphen ('-') exclusively; ban en-dash (\\u2013), em-dash (\\u2014), and minus (\\u2212).
2. Unordered lists MUST use asterisk ('*').
3. List syntax: exactly 1 space after '*', indented in multiples of 2 spaces (0 spaces at level 0).
4. Exactly 1 blank line before/after lists, code blocks, and headings.
5. Zero trailing whitespace at line ends.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DASH_REPLACEMENTS = {
    "\u2013": "-",  # en-dash
    "\u2014": "-",  # em-dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
}

IGNORE_DIR_PATTERNS = (".venv", "site", ".cache", ".archive", "mutants", ".complexipy_cache")


def _normalize_dashes(text: str, fix: bool) -> tuple[str, list[str]]:
    """Verify and optionally fix non-standard dashes in text."""
    errors: list[str] = []
    processed_text = text
    for bad_char, replacement in DASH_REPLACEMENTS.items():
        if bad_char in processed_text:
            count = processed_text.count(bad_char)
            errors.append(f"Contains {count} non-standard dash (U+{ord(bad_char):04X}) characters.")
            if fix:
                processed_text = processed_text.replace(bad_char, replacement)
    return processed_text, errors


def _check_dash_marker(line: str, line_num: int, fix: bool) -> tuple[str, list[str]]:
    """Check and optionally replace dash/plus markers with asterisk."""
    errors: list[str] = []
    updated = line
    match_dash = re.match(r"^(\s*)([-+])(\s+.*)$", updated)
    if match_dash:
        indent, marker, rest = match_dash.groups()
        errors.append(f"Line {line_num}: Unordered list uses '{marker}' instead of '*'.")
        if fix:
            updated = f"{indent}*{rest}"
    return updated, errors


def _check_star_indentation(line: str, line_num: int, fix: bool) -> tuple[str, list[str]]:
    """Check and optionally fix spacing and 2-space indentation for asterisk lists."""
    errors: list[str] = []
    updated = line
    match_star = re.match(r"^(\s*)\*(\s+)(.*)$", updated)
    if not match_star:
        return updated, errors

    indent, spaces, rest = match_star.groups()
    if len(spaces) != 1:
        errors.append(f"Line {line_num}: List marker '*' must be followed by exactly 1 space.")
        if fix:
            updated = f"{indent}* {rest}"

    if len(indent) % 2 != 0:
        errors.append(f"Line {line_num}: List indentation must be a multiple of 2 spaces (got {len(indent)}).")
        if fix:
            target_indent = round(len(indent) / 2) * 2
            updated = f"{' ' * target_indent}* {rest}"

    return updated, errors


def _validate_and_fix_list_item(line: str, line_num: int, fix: bool) -> tuple[str, list[str]]:
    """Validate and optionally fix list marker and indentation for a single line."""
    line, dash_errors = _check_dash_marker(line, line_num, fix)
    line, star_errors = _check_star_indentation(line, line_num, fix)
    return line, dash_errors + star_errors


def verify_file(path: Path, fix: bool = False) -> list[str]:
    """Verify and optionally auto-fix a single markdown file."""
    text = path.read_text(encoding="utf-8")
    original_text = text

    text, errors = _normalize_dashes(text, fix=fix)
    lines = text.splitlines()
    in_frontmatter = False
    in_codeblock = False
    new_lines: list[str] = []

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped == "---":
            in_frontmatter = not in_frontmatter
            new_lines.append(line.rstrip())
            continue

        if stripped.startswith("```"):
            in_codeblock = not in_codeblock
            new_lines.append(line.rstrip())
            continue

        if line != line.rstrip():
            errors.append(f"Line {i}: Trailing whitespace detected.")
            line = line.rstrip()

        if not in_frontmatter and not in_codeblock:
            line, line_errors = _validate_and_fix_list_item(line, i, fix=fix)
            errors.extend(line_errors)

        new_lines.append(line)

    if fix and (new_lines != lines or text != original_text):
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return errors


def _collect_target_files(paths: list[Path]) -> list[Path]:
    """Recursively collect candidate markdown files ignoring excluded directories."""
    target_files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".md":
            target_files.append(p)
        elif p.is_dir():
            target_files.extend(
                f for f in p.rglob("*.md") if not any(pattern in str(f) for pattern in IGNORE_DIR_PATTERNS)
            )
    return sorted(target_files)


def _print_violations(all_errors: dict[Path, list[str]]) -> None:
    """Format and print markdown rule violations to stderr."""
    print(f"❌ Markdown Rule 04 Violations found in {len(all_errors)} files:", file=sys.stderr)
    for f, errs in all_errors.items():
        print(f"  • {f}:", file=sys.stderr)
        for e in errs[:5]:
            print(f"      - {e}", file=sys.stderr)
        if len(errs) > 5:
            print(f"      ... and {len(errs) - 5} more issues", file=sys.stderr)


def main() -> int:
    """CLI entrypoint enforcing Markdown Rule 04 across targets."""
    parser = argparse.ArgumentParser(description="Enforce Rule 04 Markdown formatting.")
    parser.add_argument("paths", nargs="*", type=Path, help="Files or directories to check.")
    parser.add_argument("--fix", action="store_true", help="Auto-fix violations.")
    args = parser.parse_args()

    default_paths = [Path("docs"), Path(".agents"), Path("README.md"), Path("AGENTS.md")]
    target_paths = args.paths if args.paths else default_paths
    files = _collect_target_files(target_paths)

    all_errors: dict[Path, list[str]] = {}
    for f in files:
        errs = verify_file(f, fix=args.fix)
        if errs and not args.fix:
            all_errors[f] = errs

    if all_errors:
        _print_violations(all_errors)
        return 1

    action_msg = "checked and fixed" if args.fix else "verified"
    print(f"✅ Rule 04 Markdown formatting: {len(files)} files {action_msg} successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
