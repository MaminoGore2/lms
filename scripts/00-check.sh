#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in repo root."
  echo "Create it: cp .env.example .env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found in PATH"; exit 1; }
}

echo "== Checking required commands =="
need_cmd docker
need_cmd kubectl
need_cmd helm
need_cmd k3d

echo
echo "== Versions =="
docker --version
kubectl version --client --short
helm version --short
k3d version

echo
echo "== Docker connectivity check =="
docker ps >/dev/null 2>&1 && echo "OK: Docker is accessible" || {
  echo "ERROR: Docker is not accessible for current user."
  echo "Hint: ensure docker service is running and your user is in 'docker' group."
  exit 1
}

echo
echo "OK: environment looks good."
