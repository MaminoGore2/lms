#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

CLUSTER_NAME="${K3D_CLUSTER_NAME:-lms}"

echo "== Uninstall helm releases (if exist) =="
helm uninstall minio -n infra >/dev/null 2>&1 || true
helm uninstall postgres -n infra >/dev/null 2>&1 || true

echo "== Delete namespaces (optional) =="
kubectl delete namespace lms >/dev/null 2>&1 || true
kubectl delete namespace infra >/dev/null 2>&1 || true

echo "== Delete k3d cluster =="
k3d cluster delete "$CLUSTER_NAME" >/dev/null 2>&1 || true

echo "OK: environment destroyed."
