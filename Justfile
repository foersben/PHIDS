default:
    @just --list

setup:
    uv sync --all-groups
    uv run pre-commit install
    uv run task setup
    @just install-extensions

install:
    @just setup

test:
    uv run pytest

mutate:
    uv run mutmut run

ci-test:
    ./scripts/local_ci.sh tests


lint:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy src/phids/

check:
    SKIP=ruff,ruff-format,check-identity,enforce-author-identity uv run pre-commit run --all-files

act-ci:
    act -j quality-gate --secret-file .github/workflows/secrets.env

# Simulate a workflow_dispatch for docker-publish locally (skips actual push - see docker-publish.yml)
act-docker:
    act workflow_dispatch -j build-and-push --secret-file .github/workflows/secrets.env

# Simulate a tag push event locally using an event payload JSON
# act does not support --tag; use --eventpath with a push event payload instead
act-release:
    act push --eventpath .github/act-events/push-tag.json -j build-binaries --matrix os:ubuntu-latest --secret-file .github/workflows/secrets.env

format:
    uv run ruff format .

run:
    uv run phids --reload

run-numba:
    NUMBA_DISABLE_JIT=0 uv run phids --reload

benchmark:
    NUMBA_DISABLE_JIT=0 uv run pytest tests/benchmarks/ --benchmark-only

bench-compare ref1 ref2 scenario_or_dir ticks="100" repeats="2" warmup="10" extra_args="":
    uv run python scripts/run_sim_benchmark.py --compare {{ref1}} {{ref2}} {{scenario_or_dir}} {{ticks}} --repeats {{repeats}} --warmup {{warmup}} {{extra_args}}

bench-compare-jit ref1 ref2 scenario_or_dir ticks="100" repeats="2" warmup="10":
    @just bench-compare {{ref1}} {{ref2}} {{scenario_or_dir}} {{ticks}} {{repeats}} {{warmup}} --jit-only


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
        code --install-extension "$ext"; \
    done

act-profiling:
    act -j architectural-profiling --secret-file .github/workflows/secrets.env

act-complexity:
    act -j cognitive-complexity --secret-file .github/workflows/secrets.env
