#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

CLUSTER_NAME="${K3D_CLUSTER_NAME:-lms}"

echo "== Creating k3d cluster: ${CLUSTER_NAME} =="

# Важно: имя кластера в k3d/cluster.yaml должно совпадать с K3D_CLUSTER_NAME (по умолчанию lms).
if ! grep -q "name: ${CLUSTER_NAME}" k3d/cluster.yaml; then
  echo "ERROR: K3D_CLUSTER_NAME=${CLUSTER_NAME} but k3d/cluster.yaml has different metadata.name"
  echo "Fix either .env or k3d/cluster.yaml (metadata.name)."
  exit 1
fi

if k3d cluster list | awk '{print $1}' | grep -qx "$CLUSTER_NAME"; then
  echo "Cluster '$CLUSTER_NAME' already exists. Skipping creation."
else
  k3d cluster create --config k3d/cluster.yaml
fi

echo
echo "== kubectl context =="
kubectl config current-context

echo
echo "== Nodes =="
kubectl get nodes -o wide

echo
echo "OK: cluster created (nodes must be Ready)."
