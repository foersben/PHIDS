#!/usr/bin/env python3
"""Hardened validation engine enforcing Google's Open Knowledge Format (OKF v0.1)."""

from pathlib import Path
from re import findall
from sys import exit

import yaml


def check_okf_concept(file_path: Path, base_paths: list[Path]) -> list[str]:
    """Validate OKF frontmatter boundaries and cross-link graph references."""
    errors = []
    try:
        content = file_path.read_text(encoding="utf-8").strip()

        # 1. Enforce YAML Frontmatter presence
        if not content.startswith("---"):
            return ["Missing YAML frontmatter layout block."]

        parts = content.split("---", 2)
        if len(parts) < 3:
            return ["Malformed or unclosed YAML divider boundaries."]

        # 2. Validate YAML format and mandatory properties
        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as ye:
            return [f"Invalid YAML syntax syntax: {ye}"]

        if not isinstance(frontmatter, dict) or "type" not in frontmatter:
            errors.append("Missing the mandatory OKF 'type' metadata key.")

        # 3. Graph Validation: Extract and verify relative Markdown links
        body = parts[2]
        # Regex to capture standard markdown relative paths: [label](path.md)
        markdown_links = findall(r"\]\(([^:\s#)]+\.md)\)", body)

        for link in markdown_links:
            # Resolve link relative to the current file path location
            linked_file = (file_path.parent / link).resolve()

            # Ensure the linked target stays inside authorized OKF boundaries
            if not linked_file.exists():
                errors.append(f"Broken Knowledge Graph Link: Target path '{link}' does not exist.")
            elif not any(linked_file.is_relative_to(bp) for bp in base_paths):
                errors.append(f"Security Alert: Link path '{link}' escapes authorized knowledge domains.")

    except Exception as e:
        errors.append(f"System exception encountered during parse routines: {e}")

    return errors


def main() -> None:
    """Scan knowledge documentation pathways for strict OKF conformance matches."""
    directories = ["docs", ".agents"]
    base_paths = [Path(d).resolve() for d in directories if Path(d).exists()]

    global_errors = 0

    for base_path in base_paths:
        for md_file in base_path.rglob("*.md"):
            # Skip checking reserved operational logs if needed, otherwise scan all concepts
            file_errors = check_okf_concept(md_file, base_paths)
            if file_errors:
                global_errors += len(file_errors)
                print(f"❌ OKF Non-Compliance inside -> {md_file.relative_to(Path.cwd())}:")
                for err in file_errors:
                    print(f"   • {err}")

    if global_errors > 0:
        print(f"\n💥 Result: Found {global_errors} errors. Knowledge bundle rejected.")
        exit(1)

    print("✅ OKF Conformance Check: All documentation paths and link structures are pristine.")
    exit(0)


if __name__ == "__main__":
    main()
