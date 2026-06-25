#!/usr/bin/env python3
"""Script to safely identify and clean up local git branches that have no remote counterpart."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def run_git(args: Sequence[str]) -> str:
    """Execute a git command and return its stdout as a string.

    Args:
        args: Command-line arguments for git.

    Returns:
        str: Output stdout of the git command.
    """
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git {' '.join(args)}: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Prune local branches with no remote tracking counterparts."""
    print("Fetching and pruning remote tracking branches...")
    run_git(["fetch", "--prune"])

    # Get the currently checked out branch
    current_branch: str = run_git(["branch", "--show-current"])

    # Get verbose list of branches
    branches_output: str = run_git(["branch", "-vv"])

    candidates: list[str] = []

    for line in branches_output.splitlines():
        line = line.strip()
        if not line:
            continue

        # Determine if it's the current branch
        is_current: bool = line.startswith("*")
        # Remove current branch indicator
        clean_line: str = line.lstrip("* ").strip()

        # Split to get branch name
        parts: list[str] = clean_line.split()
        if not parts:
            continue
        branch_name: str = parts[0]

        # Skip main and develop
        if branch_name in ("main", "develop"):
            continue

        # Skip currently checked out branch
        if is_current or branch_name == current_branch:
            continue

        # Check tracking status
        has_upstream: bool = "[" in clean_line
        upstream_gone: bool = "[origin/" in clean_line and ": gone]" in clean_line

        if not has_upstream or upstream_gone:
            candidates.append(branch_name)

    if not candidates:
        print("No local branches found that lack a remote counterpart.")
        return

    print("\nThe following local branches have no remote counterpart:")
    for b in candidates:
        print(f"  - {b}")

    confirm: str = input("\nDo you want to delete these branches? (y/N): ").strip().lower()
    if confirm in ("y", "yes"):
        deleted_count: int = 0
        for b in candidates:
            try:
                subprocess.run(["git", "branch", "-d", b], check=True)
                deleted_count += 1
            except subprocess.CalledProcessError:
                force: str = input(f"Branch '{b}' is not fully merged. Force delete? (y/N): ").strip().lower()
                if force in ("y", "yes"):
                    subprocess.run(["git", "branch", "-D", b], check=True)
                    deleted_count += 1
        print(f"\nSuccessfully deleted {deleted_count} branches.")
    else:
        print("Aborted. No branches were deleted.")


if __name__ == "__main__":
    main()
