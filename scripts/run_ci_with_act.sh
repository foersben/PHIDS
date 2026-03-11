#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/run_ci_with_act.sh [--dryrun] [--event <event>] [--job <job>]

Rehearse the GitHub Actions workflow locally with 'act'.

Examples:
  ./scripts/run_ci_with_act.sh --dryrun
  ./scripts/run_ci_with_act.sh --job quality
  ./scripts/run_ci_with_act.sh --event push --job docs
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v act >/dev/null 2>&1; then
  echo "The 'act' CLI is not installed or not on PATH." >&2
  echo "Install it first, then rerun this script." >&2
  exit 1
fi

container_runtime_ready() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    return 0
  fi

  if command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

maybe_enable_podman_socket() {
  if ! command -v podman >/dev/null 2>&1 || ! command -v systemctl >/dev/null 2>&1; then
    return
  fi

  local runtime_dir socket_path
  runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  socket_path="$runtime_dir/podman/podman.sock"

  if [[ ! -S "$socket_path" ]]; then
    systemctl --user start podman.socket >/dev/null 2>&1 || true
  fi

  if [[ -S "$socket_path" && -z "${DOCKER_HOST:-}" ]]; then
    export DOCKER_HOST="unix://$socket_path"
  fi
}

maybe_enable_podman_socket

if ! container_runtime_ready; then
  echo "A running Docker or Podman daemon is required for 'act' rehearsal." >&2
  echo "Start your container runtime first, then rerun this script." >&2
  exit 1
fi

event_name="pull_request"
job_name=""
dry_run=0
extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dryrun|-n)
      dry_run=1
      shift
      ;;
    --event)
      event_name="$2"
      shift 2
      ;;
    --job|-j)
      job_name="$2"
      shift 2
      ;;
    --)
      shift
      extra_args+=("$@")
      break
      ;;
    *)
      extra_args+=("$1")
      shift
      ;;
  esac
done

cmd=(act "$event_name" -W .github/workflows/ci.yml)

if [[ "$dry_run" == "1" ]]; then
  cmd+=(--dryrun)
fi

if [[ -n "$job_name" ]]; then
  cmd+=(--job "$job_name")
fi

if [[ ${#extra_args[@]} -gt 0 ]]; then
  cmd+=("${extra_args[@]}")
fi

echo ">>> Running: ${cmd[*]}"
"${cmd[@]}"
