# Containers and Release Automation

This chapter documents the PHIDS runtime container, local cleanup expectations, and the GitHub
Actions workflows that publish container images and bundled binaries.

## What Exists Now

PHIDS now has three release-related surfaces in addition to the main CI workflow:

- `Dockerfile` for the runtime image,
- `docker-compose.yml` for local containerized development,
- `.github/workflows/docker-publish.yml` for publishing a GHCR image,
- `.github/workflows/release-binaries.yml` for Linux/Windows/macOS bundled binaries.

These are intentionally separate from `.github/workflows/ci.yml`, which remains the merge-gating
quality workflow.

## Local Container Run

Use Docker or a Docker-compatible Podman setup from the repository root:

```bash
docker compose up --build
```

This starts the FastAPI/HTMX application at `http://127.0.0.1:8000/`.

Current runtime behavior:

- the container executes `phids --host 0.0.0.0 --port 8000 --reload`,
- `./src` is bind-mounted into `/app/src` for live reload,
- the examples directory is mounted into `/app/examples`,
- the healthcheck probes `GET /` instead of `/api/simulation/status` because a fresh startup has no
  scenario loaded yet.

## Local Cleanup After Container Work

When local container tests finish, remove the PHIDS-specific remnants:

```bash
docker rm -f phids-local
docker rmi -f phids:test phids:local
docker image prune -f
```

Why these commands:

- `phids-local` is the named container created by `docker-compose.yml`,
- `phids:test` and `phids:local` are the image tags used during local verification,
- `docker image prune -f` removes dangling intermediate layers left by interrupted builds.

Do **not** use a broad `docker system prune -a` unless you explicitly want to clean unrelated
images and containers on your machine as well.

If you rehearse workflows locally with `act`, you may also want to remove the runner image that
`act` pulled for GitHub Actions emulation:

```bash
docker rmi ghcr.io/catthehacker/ubuntu:act-latest
```

That image is not required for normal PHIDS runtime/container usage; it is only needed for local
GitHub Actions rehearsal.

## Why Dependency Downloads Can Repeat

The repeated wheel downloads observed during testing do not necessarily mean the Dockerfile is
wrong. There are multiple independent environments involved:

1. your local development environment from `uv sync --all-extras --dev`,
2. the builder environment created inside `docker build`,
3. each GitHub Actions runner or matrix job,
4. each operating system in the release-binary workflow.

Within `Dockerfile`, PHIDS deliberately uses two `uv sync` invocations:

```bash
uv sync --frozen --no-dev --no-install-project
uv sync --frozen --no-dev
```

The first command builds a cacheable dependency-only layer. The second command installs the project
itself after `src/` has been copied. This avoids re-resolving the whole dependency graph when only
application code changes.

If the dependency layer build is interrupted before completion, the next build attempt must download
those dependencies again because the prior layer never became reusable.

## GitHub Container Publishing

The workflow `.github/workflows/docker-publish.yml`:

- logs in to `ghcr.io` using the repository `GITHUB_TOKEN`,
- lowercases the repository name for a valid image path,
- builds a multi-architecture image for `linux/amd64` and `linux/arm64`,
- publishes tags for the default branch, Git refs, semantic versions, and commit SHAs.

Typical resulting image names follow this pattern:

```text
ghcr.io/<owner>/phids:latest
ghcr.io/<owner>/phids:<git-sha>
ghcr.io/<owner>/phids:v0.1.0
```

The workflow runs on:

- pushes to `main`,
- version tags matching `v*.*.*`,
- manual workflow dispatch.

## Bundled Binary Publishing

The workflow `.github/workflows/release-binaries.yml` uses a GitHub Actions matrix over:

- `ubuntu-latest`,
- `windows-latest`,
- `macos-latest`.

Each runner:

1. installs the project dependencies with `uv`,
2. builds a PyInstaller bundle from `packaging/phids.spec`,
3. smoke-tests the launcher with `--help`,
4. starts the bundled app and probes `GET /`,
5. archives the resulting bundle,
6. uploads the archive as a workflow artifact.

On version-tag runs (`v*.*.*`), the workflow also publishes those archives as GitHub release assets.

## Packaging Inputs

The release bundle depends on:

- `src/phids/__main__.py` for the executable entrypoint,
- `pyproject.toml` for the `phids` console script,
- `packaging/phids.spec` for PyInstaller configuration,
- `src/phids/api/templates/` because the HTMX/Jinja UI must be present in the bundle,
- `examples/` and `README.md` as bundled companion resources.

## Recommended Release Flow

For a normal release:

```bash
git push origin main
git tag v0.1.0
git push origin v0.1.0
```

Expected behavior:

- the `main` push builds and publishes the container image,
- the version tag builds the container again with version tags and publishes the bundled archives to
  the GitHub release.

## Verification Notes

The container and release automation were validated with:

- `python -m phids --help`,
- focused API/UI route tests,
- workflow and packaging inspection,
- container-health smoke-check design targeting `GET /`.

If a future change adds static assets under `src/phids/api/static/`, update both the runtime image
and `packaging/phids.spec` so those assets are included in the container and bundled binaries.




