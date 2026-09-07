#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Hardened validation engine enforcing Google's Open Knowledge Format (OKF v0.2).

Validates:
- Mandatory 'type' on concept documents.
- Reserved filenames: bundle-root index.md (only okf_version allowed in frontmatter),
  subdirectory index.md (Option A: no frontmatter allowed), and log.md (chronological entries).
- Allowed lifecycle statuses: 'draft', 'stable', 'deprecated'.
- Strict ISO-8601 UTC datetimes on stale_after, generated.at, and verified.at.
- Actor string naming conventions: human:<id>, process:<id>, <producer>/<version>.
- Source resource path existence.
- Cross-document markdown link validity.
- Attested Computation mandatory runtime declaration.
- Trust tier and freshness reporting.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

# Regex patterns per OKF v0.2 specification
ISO_8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ACTOR_PATTERN = re.compile(r"^(?:human:[a-zA-Z0-9_\-]+|process:[a-zA-Z0-9_\-]+|[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\.\-]+)$")
MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^:\s#)]+\.md)(?:#[^)]+)?\)")
LOG_DATE_HEADING_PATTERN = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\b")

ALLOWED_STATUSES = {"draft", "stable", "deprecated"}


class OKFAuditStats:
    """Tracks aggregate statistics across the validated knowledge bundle."""

    def __init__(self) -> None:
        """Initialize zeroed audit statistics."""
        self.total_concepts = 0
        self.total_indexes = 0
        self.total_logs = 0
        self.human_reviewed = 0
        self.machine_confirmed = 0
        self.unverified = 0
        self.fresh = 0
        self.stale = 0
        self.no_expiry = 0


def _parse_frontmatter_block(content: str) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Extract and parse YAML frontmatter from document content.

    Returns:
        (frontmatter_dict, body_content, parse_errors)
    """
    if not content.startswith("---"):
        return None, content, ["Missing YAML frontmatter delimiter ('---') at start of file."]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content, ["Malformed or unclosed YAML frontmatter boundaries."]

    yaml_text = parts[1]
    body = parts[2]

    try:
        data = yaml.safe_load(yaml_text)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return None, body, ["YAML frontmatter must be a key-value mapping."]
        return data, body, []
    except yaml.YAMLError as exc:
        return None, body, [f"Invalid YAML syntax: {exc}"]


def _resolve_source_path(resource: str, doc_path: Path, root_path: Path) -> bool:
    """Check if a source resource path points to an existing file."""
    # Ignore web URLs, mailto, or scope descriptors with whitespace
    if resource.startswith(("http://", "https://", "mailto:")) or " " in resource:
        return True

    clean_resource = resource.split("#")[0].strip()
    if not clean_resource:
        return True

    # Check relative to document parent
    if (doc_path.parent / clean_resource).exists():
        return True
    # Check relative to workspace root
    if (root_path / clean_resource).exists():
        return True
    # Check relative to docs directory
    if (root_path / "docs" / clean_resource).exists():
        return True

    return False


def _validate_timestamp_string(val: Any, field_name: str) -> str | None:
    """Validate that a field value is formatted as strict ISO 8601 UTC."""
    if isinstance(val, datetime):
        if val.tzinfo is not None and val.tzinfo == UTC:
            return None
        return f"Field '{field_name}' must have explicit UTC 'Z' timezone."

    if not isinstance(val, str):
        return f"Field '{field_name}' must be an ISO 8601 UTC string (e.g., '2027-01-01T00:00:00Z')."

    if not ISO_8601_UTC_PATTERN.match(val):
        if DATE_ONLY_PATTERN.match(val):
            return (
                f"Field '{field_name}' has date-only format '{val}'. "
                f"Strict OKF v0.2 requires ISO 8601 UTC with 'Z' offset: '{val}T00:00:00Z'."
            )
        return (
            f"Field '{field_name}' value '{val}' is not a valid ISO 8601 UTC datetime (expected YYYY-MM-DDTHH:MM:SSZ)."
        )

    return None


def _validate_actor_string(val: Any, field_name: str) -> str | None:
    """Validate that an actor conforms to human:<id>, process:<id>, or <producer>/<version>."""
    if not isinstance(val, str):
        return f"Field '{field_name}' must be a string identifier."
    if not ACTOR_PATTERN.match(val):
        return (
            f"Field '{field_name}' actor '{val}' does not conform to OKF v0.2 conventions "
            "(must be 'human:<id>', 'process:<id>', or '<producer>/<version>')."
        )
    return None


def _validate_bundle_root_index(content: str) -> tuple[str, list[str]]:
    """Validate root index frontmatter."""
    if not content.startswith("---"):
        return content, []

    fm, body, parse_errors = _parse_frontmatter_block(content)
    errors = list(parse_errors)
    if fm is not None:
        allowed = {
            "okf_version",
            "type",
            "title",
            "status",
            "stale_after",
            "version",
            "description",
            "tags",
            "generated",
            "verified",
            "sources",
        }
        non_allowed = set(fm.keys()) - allowed
        if non_allowed:
            errors.append(f"Bundle root index.md contains unexpected frontmatter keys: {non_allowed}")
    return body, errors


def _validate_sub_index(content: str) -> tuple[str, list[str]]:
    """Validate subdirectory index has no frontmatter (Option A)."""
    if not content.startswith("---"):
        return content, []

    errors = [
        "Subdirectory index.md must not contain YAML frontmatter (OKF v0.2 §8). "
        "Retain rich overview prose and section headings directly in the Markdown body."
    ]
    parts = content.split("---", 2)
    content_to_check = parts[2] if len(parts) >= 3 else content
    return content_to_check, errors


def _validate_index_links(content_to_check: str, file_path: Path, root_path: Path) -> list[str]:
    """Validate cross-document links inside an index file."""
    errors: list[str] = []
    for link in MARKDOWN_LINK_PATTERN.findall(content_to_check):
        if link.startswith("/"):
            target = (root_path / link.lstrip("/")).resolve()
        else:
            target = (file_path.parent / link).resolve()
        if not target.exists():
            errors.append(f"Broken link in index.md: '{link}' does not exist.")
    return errors


def validate_index_document(file_path: Path, root_path: Path, is_bundle_root: bool) -> list[str]:
    """Validate an index.md file according to OKF v0.2 §8 (Option A)."""
    content = file_path.read_text(encoding="utf-8").strip()

    if is_bundle_root:
        content_to_check, errors = _validate_bundle_root_index(content)
    else:
        content_to_check, errors = _validate_sub_index(content)

    if not any(line.startswith("#") for line in content_to_check.splitlines()):
        errors.append("Index file must contain at least one Markdown section heading ('# ...').")

    errors.extend(_validate_index_links(content_to_check, file_path, root_path))
    return errors


def validate_log_document(file_path: Path) -> list[str]:
    """Validate a log.md file according to OKF v0.2 §9."""
    errors: list[str] = []
    content = file_path.read_text(encoding="utf-8").strip()

    if content.startswith("---"):
        errors.append("Log file (log.md) must not contain YAML frontmatter (OKF v0.2 §9).")

    date_headings: list[str] = []
    for line in content.splitlines():
        match = LOG_DATE_HEADING_PATTERN.match(line.strip())
        if match:
            date_str = match.group(1)
            date_headings.append(date_str)

    if not date_headings:
        errors.append("Log file must contain at least one date heading in ISO 8601 '## YYYY-MM-DD' format.")
    else:
        for i in range(len(date_headings) - 1):
            if date_headings[i] < date_headings[i + 1]:
                errors.append(
                    f"Log file date order violation: '## {date_headings[i]}' appears before "
                    f"newer entry '## {date_headings[i + 1]}'. OKF v0.2 §9 requires newest entries first."
                )

    return errors


def _validate_concept_type_and_status(fm: dict[str, Any]) -> list[str]:
    """Validate mandatory type and allowed status enum."""
    errors: list[str] = []
    doc_type = fm.get("type")
    if not doc_type or not isinstance(doc_type, str) or not doc_type.strip():
        errors.append("Missing or empty mandatory OKF frontmatter key: 'type'.")

    status = fm.get("status")
    if status is not None and status not in ALLOWED_STATUSES:
        errors.append(f"Invalid status '{status}'. OKF v0.2 allows: {', '.join(sorted(ALLOWED_STATUSES))}.")

    if doc_type == "Attested Computation":
        if "runtime" not in fm or not str(fm["runtime"]).strip():
            errors.append("Concept of type 'Attested Computation' MUST declare a 'runtime' field (§10.2).")

    return errors


def _validate_concept_stale_after(fm: dict[str, Any], stats: OKFAuditStats) -> list[str]:
    """Validate and record stale_after expiration date."""
    stale_after = fm.get("stale_after")
    if stale_after is None:
        stats.no_expiry += 1
        return []

    ts_err = _validate_timestamp_string(stale_after, "stale_after")
    if ts_err:
        return [ts_err]

    try:
        stale_str = str(stale_after)
        stale_dt = datetime.fromisoformat(stale_str.replace("Z", "+00:00"))
        if datetime.now(UTC) >= stale_dt:
            stats.stale += 1
        else:
            stats.fresh += 1
    except Exception:
        stats.no_expiry += 1
    return []


def _validate_concept_generated(fm: dict[str, Any]) -> list[str]:
    """Validate generated provenance block."""
    generated = fm.get("generated")
    if generated is None:
        return []

    if not isinstance(generated, dict):
        return ["Frontmatter 'generated' must be a mapping with {by, at}."]

    errors: list[str] = []
    if "by" in generated:
        actor_err = _validate_actor_string(generated["by"], "generated.by")
        if actor_err:
            errors.append(actor_err)
    else:
        errors.append("Key 'generated' is missing required subfield 'by'.")

    if "at" in generated:
        ts_err = _validate_timestamp_string(generated["at"], "generated.at")
        if ts_err:
            errors.append(ts_err)
    return errors


def _validate_single_verification(entry: Any, idx: int) -> tuple[bool, bool, list[str]]:
    """Validate a single verified entry. Returns (is_human, is_machine, errors)."""
    if not isinstance(entry, dict):
        return False, False, [f"verified[{idx}] must be a mapping."]

    errors: list[str] = []
    is_human = False
    is_machine = False

    if "by" in entry:
        actor_err = _validate_actor_string(entry["by"], f"verified[{idx}].by")
        if actor_err:
            errors.append(actor_err)
        elif str(entry["by"]).startswith("human:"):
            is_human = True
        else:
            is_machine = True
    else:
        errors.append(f"verified[{idx}] is missing required subfield 'by'.")

    if "at" in entry:
        ts_err = _validate_timestamp_string(entry["at"], f"verified[{idx}].at")
        if ts_err:
            errors.append(ts_err)

    return is_human, is_machine, errors


def _validate_concept_verified(fm: dict[str, Any], stats: OKFAuditStats) -> list[str]:
    """Validate verified provenance entries and record trust tier."""
    verified = fm.get("verified")
    if verified is None:
        stats.unverified += 1
        return []

    verified_list = [verified] if isinstance(verified, dict) else verified
    if not isinstance(verified_list, list):
        stats.unverified += 1
        return ["Frontmatter 'verified' must be a mapping or a list of mappings."]

    errors: list[str] = []
    has_human = False
    has_machine = False

    for idx, entry in enumerate(verified_list):
        h, m, errs = _validate_single_verification(entry, idx)
        if h:
            has_human = True
        if m:
            has_machine = True
        errors.extend(errs)

    if has_human:
        stats.human_reviewed += 1
    elif has_machine:
        stats.machine_confirmed += 1
    else:
        stats.unverified += 1

    return errors


def _validate_concept_sources(fm: dict[str, Any], file_path: Path, root_path: Path) -> list[str]:
    """Validate sources resource paths."""
    sources = fm.get("sources")
    if sources is None:
        return []
    if not isinstance(sources, list):
        return ["Frontmatter 'sources' must be a list of source entries."]

    errors: list[str] = []
    for idx, s in enumerate(sources):
        if not isinstance(s, dict):
            errors.append(f"sources[{idx}] must be a mapping with 'resource'.")
            continue
        resource = s.get("resource")
        if not resource or not isinstance(resource, str):
            errors.append(f"sources[{idx}] is missing required 'resource' string.")
        elif not _resolve_source_path(resource, file_path, root_path):
            errors.append(f"Broken source resource in sources[{idx}]: '{resource}' does not exist.")
    return errors


def _validate_concept_links(
    body: str,
    file_path: Path,
    root_path: Path,
    base_paths: list[Path],
) -> list[str]:
    """Validate cross-document Markdown links."""
    errors: list[str] = []
    for link in MARKDOWN_LINK_PATTERN.findall(body):
        if link.startswith(("http://", "https://", "#")):
            continue

        if link.startswith("/"):
            target = (root_path / link.lstrip("/")).resolve()
        else:
            target = (file_path.parent / link).resolve()

        if not target.exists():
            errors.append(f"Broken Markdown Link: target '{link}' does not exist.")
        elif not any(target.is_relative_to(bp) for bp in base_paths):
            errors.append(f"Security Alert: Link path '{link}' escapes authorized knowledge bundle domains.")
    return errors


def validate_concept_document(
    file_path: Path,
    root_path: Path,
    base_paths: list[Path],
    stats: OKFAuditStats,
) -> list[str]:
    """Validate a concept document according to OKF v0.2 specifications."""
    content = file_path.read_text(encoding="utf-8").strip()
    fm, body, parse_errors = _parse_frontmatter_block(content)
    if parse_errors:
        return parse_errors
    if fm is None:
        return ["Failed to read frontmatter mapping."]

    stats.total_concepts += 1
    errors: list[str] = []
    errors.extend(_validate_concept_type_and_status(fm))
    errors.extend(_validate_concept_stale_after(fm, stats))
    errors.extend(_validate_concept_generated(fm))
    errors.extend(_validate_concept_verified(fm, stats))
    errors.extend(_validate_concept_sources(fm, file_path, root_path))
    errors.extend(_validate_concept_links(body, file_path, root_path, base_paths))
    return errors


def auto_fix_timestamps(files: list[Path]) -> int:
    """Normalize date-only strings YYYY-MM-DD to strict ISO 8601 UTC in frontmatter."""
    fixed_count = 0
    date_regex = re.compile(r'^(stale_after:\s*["\']?)(\d{4}-\d{2}-\d{2})(["\']?)$', re.MULTILINE)

    for file_path in files:
        if file_path.name in ("index.md", "log.md"):
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            fm_text = parts[1]
            new_fm_text = date_regex.sub(r"\1\2T00:00:00Z\3", fm_text)
            if new_fm_text != fm_text:
                new_content = f"---{new_fm_text}---{parts[2]}"
                file_path.write_text(new_content, encoding="utf-8")
                fixed_count += 1
        except Exception as exc:
            print(f"Warning: Failed to auto-fix {file_path}: {exc}")

    return fixed_count


def _validate_single_bundle_file(
    md_file: Path,
    root_path: Path,
    base_paths: list[Path],
    docs_root_index: Path,
    stats: OKFAuditStats,
) -> list[str]:
    """Validate an individual markdown file based on file role."""
    if md_file.name == "index.md":
        stats.total_indexes += 1
        is_root = (md_file.resolve() == docs_root_index) or (md_file.parent.resolve() == root_path.resolve())
        return validate_index_document(md_file, root_path, is_bundle_root=is_root)

    if md_file.name == "log.md":
        stats.total_logs += 1
        return validate_log_document(md_file)

    return validate_concept_document(md_file, root_path, base_paths, stats)


def scan_bundle(
    target_files: list[Path],
    root_path: Path,
    base_paths: list[Path],
) -> tuple[int, OKFAuditStats]:
    """Scan and validate all supplied markdown files."""
    total_errors = 0
    stats = OKFAuditStats()
    docs_root_index = (root_path / "docs" / "index.md").resolve()

    for md_file in target_files:
        if not md_file.exists() or not md_file.is_file():
            continue

        file_posix = md_file.as_posix()
        if "docs/legacy/" in file_posix or "site/" in file_posix:
            continue

        file_errors = _validate_single_bundle_file(md_file, root_path, base_paths, docs_root_index, stats)
        if file_errors:
            total_errors += len(file_errors)
            rel_display = md_file.relative_to(root_path) if md_file.is_relative_to(root_path) else md_file
            print(f"❌ OKF Non-Compliance inside -> {rel_display}:")
            for err in file_errors:
                print(f"   • {err}")

    return total_errors, stats


def main() -> None:
    """CLI entry point for OKF v0.2 validation engine."""
    parser = argparse.ArgumentParser(description="Google Open Knowledge Format (OKF v0.2) Conformance Validator")
    parser.add_argument("files", nargs="*", help="Specific markdown files to validate (defaults to docs/ and .agents/)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix date-only timestamps to strict ISO 8601 UTC")
    parser.add_argument("--root", default=".", help="Root workspace directory")
    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    base_dirs = [root_path / "docs", root_path / ".agents"]
    base_paths = [d for d in base_dirs if d.exists()]

    if args.files:
        target_files = [Path(f).resolve() for f in args.files]
    else:
        target_files = []
        for base in base_paths:
            target_files.extend(base.rglob("*.md"))

    if args.fix:
        fixed_count = auto_fix_timestamps(target_files)
        print(f"🛠️  Auto-fixed {fixed_count} files with normalized ISO 8601 UTC timestamps.")

    total_errors, stats = scan_bundle(target_files, root_path, base_paths)

    print("\n" + "=" * 65)
    print("📊 OKF v0.2 Knowledge Bundle Audit Summary")
    print("=" * 65)
    print(f"  • Total Concept Documents: {stats.total_concepts}")
    print(f"  • Total Index Listings:    {stats.total_indexes}")
    print(f"  • Total Update Logs:       {stats.total_logs}")
    print("  Trust Tiers (§5.3):")
    print(f"    - Human-Reviewed:        {stats.human_reviewed}")
    print(f"    - Machine-Confirmed:     {stats.machine_confirmed}")
    print(f"    - Unverified:            {stats.unverified}")
    print("  Freshness Status (§5.5):")
    print(f"    - Fresh:                 {stats.fresh}")
    print(f"    - Stale:                 {stats.stale}")
    print(f"    - No Expiry Declared:    {stats.no_expiry}")
    print("=" * 65)

    if total_errors > 0:
        print(f"\n💥 Result: Found {total_errors} compliance violations. Knowledge bundle rejected.\n")
        sys.exit(1)

    print("\n✅ OKF Conformance Check: All documentation paths and knowledge invariants are pristine.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
