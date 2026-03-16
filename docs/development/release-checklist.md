# Release Checklist

This chapter defines the canonical PHIDS release procedure for publishing a new semantic version,
updating the public documentation site, and shipping binary/container artifacts from one audited
source lineage.

The release process is intentionally split into two boundaries:

1. **Promotion boundary** (`develop` -> `main`): confirms that the release candidate has passed all
   quality gates and documentation checks.
2. **Publication boundary** (`main` tag push): triggers immutable release automation for binaries,
   container images, and release metadata.

These boundaries preserve reproducibility and make post-release forensics tractable.

## Preconditions

Before opening a release PR:

- project version is updated consistently (`pyproject.toml`, API metadata),
- release-relevant documentation is updated (`README.md`, development/runbook docs),
- quality gates pass locally (`ruff`, `mypy`, `pytest`, `mkdocs --strict`),
- no unrelated workspace artifacts are staged.

Recommended validation commands:

```bash
uv sync --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv run mkdocs build --strict
```

## Promotion to main

1. Push release-prep commits to `develop`.
2. Open a pull request from `develop` to `main`.
3. Wait for all required CI checks to pass.
4. Merge using the repository's protected-branch policy.

After merge, documentation deployment is handled by `.github/workflows/docs-pages.yml` because it
runs on `push` to `main`.

## Tag and publish

After `main` includes the merged release commit:

```bash
git checkout main
git pull --ff-only origin main
git tag v0.4.0
git push origin v0.4.0
```

The tag triggers:

- `.github/workflows/release-binaries.yml` (Linux/Windows/macOS bundled executables),
- `.github/workflows/docker-publish.yml` (multi-arch GHCR image publish).

## Post-release verification

Validate all publication surfaces:

- GitHub release page exists for `v0.4.0` and contains archived binaries,
- GHCR image tags include `v0.4.0`, `0.4`, `latest`, and `sha` variants,
- GitHub Pages serves the updated docs from `main`,
- README and docs release references match the shipped semantic version.

## Failure handling

If a publish workflow fails:

- do not retag to a different commit silently,
- fix forward on `develop`,
- promote to `main` again,
- cut a new tag (`v0.4.1`) unless policy explicitly allows rerunning the same tag with no content drift.
