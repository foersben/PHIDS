# List all available recipes categorized by group
default:
    @just --list

# Full project bootstrap: sync dependencies, install git hooks, and run initial ETL
[group("setup")]
setup:
    uv sync --all-groups
    uv run pre-commit install
    uv run task setup
    @just install-extensions
    @just etl

# Alias for setup: bootstrap project dependencies and environment
[group("setup")]
install:
    @just setup

# Install recommended VS Code extensions declared in .vscode/extensions.json
[group("setup")]
install-extensions:
    @jq -r '.recommendations[]' .vscode/extensions.json | while read -r ext; do \
        code --install-extension "$ext"; \
    done

# Run the full Pytest test suite across all groups
[group("testing")]
test:
    uv run --all-groups pytest

# Run biological and scientific invariant tests (-m scientific_invariant)
[group("testing")]
test-scientific:
    uv run --all-groups pytest --no-cov -m scientific_invariant

# Run JIT vs pure-Python numerical parity tests (-m jit_parity)
[group("testing")]
test-parity:
    uv run --all-groups pytest --no-cov -m jit_parity

# Run Zarr replay bit-exactness and deterministic I/O tests
[group("testing")]
test-replay:
    uv run --all-groups pytest --no-cov tests/e2e/replay_and_io/test_zarr_replay_bit_exactness.py

# Run local CI test orchestration script (scripts/local_ci.sh tests)
[group("testing")]
ci-test:
    ./scripts/local_ci.sh tests

# Run mutation testing with Mutmut across core simulation kernels
[group("testing")]
mutate:
    uv run mutmut run

# Run causal Data-Flow Matrix trace tests against markdown doc tables
[group("data-flow-matrix")]
test-matrix:
    uv run pytest --no-cov tests/integration/scientific_invariants/test_causal_data_flow_matrices.py -v

# Audit scientific model docs for Data-Flow Matrix coverage and bilateral links
[group("data-flow-matrix")]
audit-matrix:
    uv run python scripts/audit_matrix_coverage.py

# Verify 1:1 point-by-point numerical parity between doc tables and runtime traces
[group("data-flow-matrix")]
verify-matrix:
    uv run python scripts/verify_matrix_trace_parity.py --all

# Generate interactive OKF knowledge graph visualization (docs/viz.html)
[group("data-flow-matrix")]
visualize-okf:
    uv run python scripts/visualize_okf.py

# Validate Open Knowledge Format (OKF v0.2) frontmatter, paths, and freshness across docs
[group("data-flow-matrix")]
validate-okf:
    uv run python scripts/validate_okf.py

# Run Ruff linter (--fix), Ruff formatter, and strict Mypy type validation
[group("quality")]
lint:
    uv run ruff check --fix .
    uv run ruff format .
    uv run mypy src/phids/

# Format all Python source code with Ruff
[group("quality")]
format:
    uv run ruff format .

# Run pre-commit hooks (excluding ruff and author identity) across all files
[group("quality")]
check:
    SKIP=ruff,ruff-format,check-identity,enforce-author-identity uv run pre-commit run --all-files

# Run cognitive complexity analysis with Complexipy across the repository
[group("quality")]
complexity:
    uvx complexipy . --failed

# Run local cognitive complexity analysis with Complexipy
[group("quality")]
complexity-local:
    uvx complexipy . --failed

# Run CI cognitive complexity analysis with Complexipy
[group("quality")]
complexity-ci:
    uvx complexipy . --failed

# Launch PHIDS FastAPI simulation server with auto-reload
[group("simulation-and-docs")]
run:
    uv run phids --reload

# Build static scientific and architectural documentation with Zensical
[group("simulation-and-docs")]
docs:
    uv run zensical build

# Build and serve live Zensical documentation on localhost:9000
[group("simulation-and-docs")]
serve:
    uv run zensical build
    uv run zensical serve -a localhost:9000

# Execute pytest-benchmark performance suite with Numba JIT enabled
[group("benchmarks")]
benchmark:
    NUMBA_DISABLE_JIT=0 uv run pytest --no-cov tests/benchmarks/ --benchmark-only

[doc("Compare simulation performance between two git refs or scenarios.\nUsage: just bench-compare <ref1> <ref2> <scenario_or_dir> [ticks='100'] [repeats='2'] [warmup='10'] [extra_args='']\nExample: just bench-compare main develop scenarios/ 100 2")]
[group("benchmarks")]
bench-compare ref1 ref2 scenario_or_dir ticks="100" repeats="2" warmup="10" extra_args="":
    uv run python scripts/run_sim_benchmark.py --compare {{ ref1 }} {{ ref2 }} {{ scenario_or_dir }} {{ ticks }} --repeats {{ repeats }} --warmup {{ warmup }} {{ extra_args }}

[doc("Compare JIT-only simulation benchmark performance between two git refs.\nUsage: just bench-compare-jit <ref1> <ref2> <scenario_or_dir> [ticks='100'] [repeats='2'] [warmup='10']")]
[group("benchmarks")]
bench-compare-jit ref1 ref2 scenario_or_dir ticks="100" repeats="2" warmup="10":
    @just bench-compare {{ ref1 }} {{ ref2 }} {{ scenario_or_dir }} {{ ticks }} {{ repeats }} {{ warmup }} --jit-only

# Run core empirical ETL pipeline (BIEN/LEDA/GIFT extraction)
[group("data-pipeline")]
etl:
    uv run --group pipeline python src/data_pipeline/run_all.py

# Force-refresh and re-download all core empirical datasets
[group("data-pipeline")]
etl-refresh:
    uv run --group pipeline python src/data_pipeline/run_all.py --force-refresh

# Extended academic pipeline (opt-in: requires accepting NC license terms)
[group("data-pipeline")]
etl-extended:
    PHIDS_EXTENDED_MODE=1 uv run --group pipeline python src/data_pipeline/run_extended.py

# Force-refresh and re-download extended academic datasets under NC terms
[group("data-pipeline")]
etl-extended-refresh:
    PHIDS_EXTENDED_MODE=1 uv run --group pipeline python src/data_pipeline/run_extended.py --force-refresh

# Publish core empirical dataset (CC0/CC-BY) to Hugging Face repository
[group("data-pipeline")]
etl-publish-core:
    uv run --group pipeline python src/data_pipeline/run_all.py --publish

# Publish extended academic dataset (CC-BY-NC-SA 4.0) to Hugging Face repository
[group("data-pipeline")]
etl-publish-extended:
    PHIDS_EXTENDED_MODE=1 uv run --group pipeline python src/data_pipeline/run_extended.py --publish

# Run GitHub Actions quality-gate workflow locally using nektos/act
[group("ci-act")]
act-ci:
    act -j quality-gate --secret-file .github/workflows/secrets.env

# Simulate workflow_dispatch for docker-publish locally (skips push)
[group("ci-act")]
act-docker:
    act workflow_dispatch -j build-and-push --secret-file .github/workflows/secrets.env

# Simulate tag push release build locally via event payload JSON
[group("ci-act")]
act-release:
    act push --eventpath .github/act-events/push-tag.json -j build-binaries --matrix os:ubuntu-latest --secret-file .github/workflows/secrets.env

# Run architectural profiling GitHub Actions workflow locally via act
[group("ci-act")]
act-profiling:
    act -j architectural-profiling --secret-file .github/workflows/secrets.env

# Run cognitive complexity GitHub Actions workflow locally via act
[group("ci-act")]
act-complexity:
    act -j cognitive-complexity --secret-file .github/workflows/secrets.env

# Clean all build artifacts, caches, and test runs
[group("maintenance")]
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    rm -rf .cache site build dist .pytest_cache .mypy_cache .ruff_cache .hypothesis .coverage
    rm -rf .hypothesis .coverage
    @just clean-act
    @just docker-clean

# Prune dangling Docker containers and networks labeled by nektos/act
[group("maintenance")]
clean-act:
    @docker container prune --force --filter "label=actor=act" 2>/dev/null || true
    @docker network prune --force --filter "label=actor=act" 2>/dev/null || true

# Remove local PHIDS Docker containers and images
[group("maintenance")]
docker-clean:
    @docker rm -f phids-local 2>/dev/null || true
    @docker rmi -f phids:test phids:local 2>/dev/null || true
    @docker image prune -f
