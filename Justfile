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

check:
    uv run pre-commit run --all-files

format:
    uv run ruff format .

run:
    uv run phids --reload

clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf .cache site

docs:
    uv run zensical build

serve:
    uv run zensical build
    uv run zensical serve -a localhost:9000

    
install-extensions:
    @jq -r '.recommendations[]' .vscode/extensions.json | while read -r ext; do \
        code --install-extension "$$ext"; \
    done