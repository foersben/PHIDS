# SPDX-FileCopyrightText: 2026 Benjamin Förster
# SPDX-License-Identifier: EUPL-1.2 OR LicenseRef-PHIDS-Commercial

"""Unit tests for the Google Open Knowledge Format (OKF v0.2) validation engine."""

import tempfile
from pathlib import Path

import pytest
from scripts.validate_okf import (
    OKFAuditStats,
    auto_fix_timestamps,
    validate_concept_document,
    validate_index_document,
    validate_log_document,
)


@pytest.fixture
def temp_workspace() -> Path:
    """Create a temporary directory structure mimicking an OKF repository."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        docs_dir = root / "docs"
        docs_dir.mkdir(parents=True)
        agents_dir = root / ".agents"
        agents_dir.mkdir(parents=True)
        yield root


def test_validate_concept_valid(temp_workspace: Path) -> None:
    """Assert that a fully compliant concept document passes validation."""
    doc_path = temp_workspace / "docs" / "test_concept.md"
    doc_path.write_text(
        """---
type: Concept
title: Test Concept
status: stable
stale_after: "2027-01-01T00:00:00Z"
generated: {by: process:ci-builder, at: "2026-09-01T12:00:00Z"}
verified:
  - {by: human:tester, at: "2026-09-02T12:00:00Z"}
---

# Test Concept Body

This is valid concept prose.
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert errors == []
    assert stats.total_concepts == 1
    assert stats.human_reviewed == 1
    assert stats.fresh == 1


def test_validate_concept_missing_type(temp_workspace: Path) -> None:
    """Assert that missing mandatory 'type' triggers a compliance error."""
    doc_path = temp_workspace / "docs" / "bad_type.md"
    doc_path.write_text(
        """---
title: Bad Document
status: stable
---

# Content
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("mandatory OKF frontmatter key: 'type'" in e for e in errors)


def test_validate_concept_invalid_status(temp_workspace: Path) -> None:
    """Assert that invalid lifecycle status enum values are rejected."""
    doc_path = temp_workspace / "docs" / "bad_status.md"
    doc_path.write_text(
        """---
type: Concept
status: realized
---

# Content
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("Invalid status 'realized'" in e for e in errors)


def test_validate_concept_invalid_timestamp(temp_workspace: Path) -> None:
    """Assert that non-UTC or date-only timestamps are flagged."""
    doc_path = temp_workspace / "docs" / "bad_date.md"
    doc_path.write_text(
        """---
type: Concept
stale_after: "2027-01-01"
---

# Content
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("Strict OKF v0.2 requires ISO 8601 UTC with 'Z' offset" in e for e in errors)


def test_validate_concept_invalid_actor(temp_workspace: Path) -> None:
    """Assert that actor strings not conforming to OKF conventions are rejected."""
    doc_path = temp_workspace / "docs" / "bad_actor.md"
    doc_path.write_text(
        """---
type: Concept
generated: {by: "Random Guy", at: "2026-09-01T12:00:00Z"}
---

# Content
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("actor 'Random Guy' does not conform" in e for e in errors)


def test_validate_concept_broken_source_resource(temp_workspace: Path) -> None:
    """Assert that dangling source resources are reported as broken."""
    doc_path = temp_workspace / "docs" / "broken_source.md"
    doc_path.write_text(
        """---
type: Concept
sources:
  - id: nonexistent
    resource: non_existent_file.py
---

# Content
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("Broken source resource" in e for e in errors)


def test_validate_attested_computation_runtime(temp_workspace: Path) -> None:
    """Assert that concepts of type 'Attested Computation' mandate a 'runtime' field."""
    doc_path = temp_workspace / "docs" / "computation.md"
    doc_path.write_text(
        """---
type: Attested Computation
title: Defense Cascade
---

# Computation
""",
        encoding="utf-8",
    )

    stats = OKFAuditStats()
    errors = validate_concept_document(doc_path, temp_workspace, [temp_workspace / "docs"], stats)
    assert any("Attested Computation' MUST declare a 'runtime' field" in e for e in errors)


def test_validate_index_document_option_a(temp_workspace: Path) -> None:
    """Assert Option A rules: bundle-root allows okf_version, subdirectory rejects frontmatter."""
    # 1. Bundle root index with okf_version
    root_index = temp_workspace / "docs" / "index.md"
    root_index.write_text(
        """---
okf_version: "0.2"
---

# Bundle Root

* [Section 1](section1/index.md) - Section description
""",
        encoding="utf-8",
    )
    root_errors = validate_index_document(root_index, temp_workspace, is_bundle_root=True)
    # Target doesn't exist so it will flag broken link, but no frontmatter error
    assert not any("Subdirectory index.md must not contain YAML frontmatter" in e for e in root_errors)

    # 2. Subdirectory index WITH frontmatter (must fail per Option A)
    sub_index = temp_workspace / "docs" / "scientific_model" / "index.md"
    sub_index.parent.mkdir(parents=True)
    sub_index.write_text(
        """---
type: Scientific Model
title: Sub Overview
---

# Subdirectory Overview
""",
        encoding="utf-8",
    )
    sub_errors = validate_index_document(sub_index, temp_workspace, is_bundle_root=False)
    assert any("Subdirectory index.md must not contain YAML frontmatter" in e for e in sub_errors)

    # 3. Subdirectory index WITHOUT frontmatter (must pass)
    sub_index.write_text(
        """# Subdirectory Overview

Rich floating text explaining scientific dynamics in depth.
""",
        encoding="utf-8",
    )
    sub_clean_errors = validate_index_document(sub_index, temp_workspace, is_bundle_root=False)
    assert sub_clean_errors == []


def test_validate_log_document(temp_workspace: Path) -> None:
    """Assert log.md validation rules for chronological order and no frontmatter."""
    log_file = temp_workspace / "docs" / "log.md"

    # Valid chronological log
    log_file.write_text(
        """# Knowledge Bundle Log

## 2026-09-06
* **Update**: Added OKF v0.2 test suite.

## 2026-08-01
* **Creation**: Initial bundle setup.
""",
        encoding="utf-8",
    )
    errors = validate_log_document(log_file)
    assert errors == []

    # Out of order dates
    bad_log = temp_workspace / "docs" / "bad_log.md"
    bad_log.write_text(
        """# Bad Log

## 2026-08-01
* Old entry first.

## 2026-09-06
* New entry second.
""",
        encoding="utf-8",
    )
    bad_errors = validate_log_document(bad_log)
    assert any("Log file date order violation" in e for e in bad_errors)


def test_auto_fix_timestamps(temp_workspace: Path) -> None:
    """Assert that auto_fix_timestamps converts date-only stale_after strings."""
    doc_path = temp_workspace / "docs" / "needs_fix.md"
    doc_path.write_text(
        """---
type: Concept
stale_after: "2027-01-01"
---

# Content
""",
        encoding="utf-8",
    )

    fixed = auto_fix_timestamps([doc_path])
    assert fixed == 1
    content = doc_path.read_text(encoding="utf-8")
    assert 'stale_after: "2027-01-01T00:00:00Z"' in content
