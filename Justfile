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

lint:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy src/phids/

format:
    uv run ruff format .

run:
    uv run phids --reload

clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf .pytest_cache .mypy_cache .coverage htmlcov .cache/uv site .ruff_cache .hypothesis .benchmarks .cache

docs:
    uv run zensical build

install-extensions:
    @jq -r '.recommendations[]' .vscode/extensions.json | while read -r ext; do \
        code --install-extension "$$ext"; \
    done