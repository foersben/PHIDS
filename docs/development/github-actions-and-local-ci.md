# GitHub Actions and Local CI Rehearsal

This chapter documents the current CI strategy for PHIDS and how to rehearse it locally before
spending GitHub Actions minutes.

PHIDS now intentionally standardizes on Python 3.12+ and avoids automatic GitHub Actions runs on
every in-progress branch commit.

## CI Design Goal

PHIDS needs CI that protects three things at the same time:

- architectural correctness,
- contributor hygiene and static checks,
- documentation buildability.

The merge-gating workflow still does **not** run inside a PHIDS-specific CI container. It uses
GitHub-hosted runners directly and reserves containers for:

- local workflow emulation with `act`,
- the runtime image published to GHCR,
- the release-binary packaging flow described in
  [`containers-and-release-automation.md`](containers-and-release-automation.md).

## Current Recommendation on Containers

### GitHub-hosted CI

Use standard GitHub Actions runners for `.github/workflows/ci.yml`:

- `runs-on: ubuntu-latest`

This keeps the merge-gating pipeline simple while still allowing separate runtime/release
automation to exist where it adds value.

### Local rehearsal

Use [`act`](https://github.com/nektos/act) for local workflow rehearsal.

With the current workflow shape, `act` starts **one runner container per CI job**. In other words,
PHIDS does not currently need one long-lived project container plus service containers; it only needs
runner containers that emulate GitHub-hosted jobs.

## Trigger Policy

The main CI workflow is intentionally narrow.

It runs on:

- pushes to `main`,
- pull requests targeting `main`,
- manual `workflow_dispatch` runs.

It does **not** run on every branch push, and it therefore does **not** automatically run on
`develop`.

## Published Documentation Site

The MkDocs site is published through `.github/workflows/docs-pages.yml`.

- live URL: `https://foersben.github.io/PHIDS/`
- deploy triggers: pushes to `main` and manual `workflow_dispatch`
- build gate: `uv run mkdocs build --strict` before artifact upload/deploy

## Current Job Layout

The active workflow is split into focused jobs so failures are easier to interpret and the expensive
whole-suite test run does not block unrelated feedback.

| Job | Python | Purpose | Command |
| --- | --- | --- | --- |
| `quality` | 3.12 | Green repository hygiene checks | `uv run ruff check . && uv run ruff format --check .` |
| `tests-py312` | 3.12 | Canonical whole-suite validation with coverage and benchmark tests | `uv run pytest` |
| `docs` | 3.12 | Documentation buildability and broken-link/navigation protection | `uv run mkdocs build --strict` |

## Why the Jobs Are Split This Way

### Quality job

The current repository-wide green lane is Ruff lint plus Ruff format check. Full `pre-commit`,
`mypy`, and `pydocstyle` are still useful local cleanup tools, but they are not currently part of
the merge-blocking workflow because the repository still carries pre-existing type/docstyle debt.

### Full test suite on Python 3.12

Python 3.12 is the main merge-confidence interpreter because:

- the project targets `py312` in Ruff,
- the local contributor guidance already prefers Python 3.12,
- this job runs the complete `pytest` configuration including coverage and benchmark files.

### No separate Python 3.11 compatibility lane

PHIDS now declares `requires-python = ">=3.12"` and no longer carries a dedicated Python 3.11
compatibility smoke job. This reduces CI cost and avoids maintaining a floor the project no longer
claims to support.

### Strict docs build as a first-class job

Documentation is a maintained product surface in PHIDS, not an afterthought. A separate docs job
makes failures obvious and keeps the docs corpus under the same review discipline as the code.

## Benchmarks in CI

The dedicated benchmark files remain in the canonical `uv run pytest` job because they currently act
as correctness-plus-performance-sanity checks rather than time-budget enforcement jobs.

That means CI still executes:

- `tests/test_flow_field_benchmark.py`
- `tests/test_spatial_hash_benchmark.py`

through the normal test suite.

## Local Rehearsal Paths

PHIDS now supports two local rehearsal modes.

### 1. Fast local parity on your current interpreter

Use the helper script:

```bash
./scripts/local_ci.sh all
```

You can also run specific slices:

```bash
./scripts/local_ci.sh quality
./scripts/local_ci.sh tests
./scripts/local_ci.sh docs
```

This path is best when you want quick confirmation that the repo passes the same top-level commands
without waiting for GitHub.

### 2. Containerized workflow rehearsal with `act`

Use the wrapper script:

```bash
./scripts/run_ci_with_act.sh --dryrun
./scripts/run_ci_with_act.sh --job quality
./scripts/run_ci_with_act.sh --job tests-py312
./scripts/run_ci_with_act.sh --job docs
```

This path is best when you want to verify the actual GitHub Actions workflow structure locally.
It still requires a running Docker or Podman daemon because `act` executes jobs inside runner
containers, even for dry runs. The helper script will attempt to start `podman.socket` through user
systemd automatically when Podman is installed and the socket is not already active.

## What `act` Uses Here

The repository-level `.actrc` maps `ubuntu-latest` to a standard `act` runner image. That gives local
containerized execution without introducing a PHIDS-specific Docker image.

Current implication:

- if you run the whole workflow with `act`, the workflow will use up to three runner containers,
  matching the three jobs,
- there are currently no service containers in the workflow.

## Related Runtime and Release Automation

PHIDS now also maintains two non-CI workflows:

- `.github/workflows/docker-publish.yml`
- `.github/workflows/release-binaries.yml`

These do not replace the CI workflow. They serve different purposes:

- `docker-publish.yml` publishes the runtime image to `ghcr.io` on version tags or manual runs,
- `release-binaries.yml` builds bundled Linux, Windows, and macOS archives.

That split keeps merge gating focused while still making distribution artifacts reproducible.

## Why Dependency Downloads Repeat Across Workflows

Repeated dependency downloads are expected across the current automation surfaces because each one
creates an isolated environment:

- local `uv sync` on the developer machine,
- `act` runner containers,
- each GitHub Actions job in `.github/workflows/ci.yml`,
- the Docker builder image in `Dockerfile`,
- each operating-system matrix runner in `release-binaries.yml`.

Inside `Dockerfile`, PHIDS intentionally performs a dependency-only sync first and then installs the
project after copying `src/`. This preserves a reusable dependency layer even though it looks like a
two-step install.

## When a Dedicated Project Container Would Be Worth Adding Later

A PHIDS-specific CI container would become worthwhile only if one or more of these become true:

- the dependency graph gains significant native/system package complexity,
- the workflow requires reproducible OS-level scientific libraries not well covered by the hosted
  runners,
- CI startup cost from repeated environment setup becomes the dominant bottleneck.

That is not the current state of the repository.

## Suggested Contributor Routine

For normal work, a practical sequence is:

```bash
uv sync --all-extras --dev
./scripts/local_ci.sh all
./scripts/run_ci_with_act.sh --dryrun
```

Then, if you want to rehearse a specific GitHub Actions job locally:

```bash
./scripts/run_ci_with_act.sh --job tests-py312
```

## Verified Current-State Evidence

- `.github/workflows/ci.yml`
- `.actrc`
- `scripts/local_ci.sh`
- `scripts/run_ci_with_act.sh`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `README.md`
- `docs/development/testing-strategy-and-benchmark-policy.md`

## Where to Read Next

- For the broader contributor workflow: [`contribution-workflow-and-quality-gates.md`](contribution-workflow-and-quality-gates.md)
- For the testing rationale behind the selected jobs: [`testing-strategy-and-benchmark-policy.md`](testing-strategy-and-benchmark-policy.md)
- For the current documentation handoff/backlog: [`documentation-status-and-open-work.md`](documentation-status-and-open-work.md)

