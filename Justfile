default:
    @just --list

setup:
    uv sync --all-groups
    uv run pre-commit install
    @just install-extensions

install:
    @just setup

test:
    uv run pytest

ci-test:
    ./scripts/local_ci.sh tests


lint:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy src/phids/

check:
    uv run pre-commit run --all-files

act-ci:
    act -j quality-gate --secret-file .github/workflows/secrets.env

act-docker:
    act workflow_dispatch -j build-and-push --secret-file .github/workflows/secrets.env

act-release:
    act push --tag v0.1.0 -j build-binaries --matrix os:ubuntu-latest --secret-file .github/workflows/secrets.env

format:
    uv run ruff format .

run:
    uv run phids --reload

clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf .cache site build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis .coverage
    rm -rf .hypothesis .coverage
    @just clean-act
    @just docker-clean

clean-act:
    @docker container prune --force --filter "label=actor=act" 2>/dev/null || true
    @docker network prune --force --filter "label=actor=act" 2>/dev/null || true

docker-clean:
    @docker rm -f phids-local 2>/dev/null || true
    @docker rmi -f phids:test phids:local 2>/dev/null || true
    @docker image prune -f

docs:
    uv run zensical build

serve:
    uv run zensical build
    uv run zensical serve -a localhost:9000


install-extensions:
    @jq -r '.recommendations[]' .vscode/extensions.json | while read -r ext; do \
        code --install-extension "$$ext"; \
    done
