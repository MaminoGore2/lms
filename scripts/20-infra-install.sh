#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

wait_for_pods_by_label() {
  local ns="$1"
  local selector="$2"
  local timeout_sec="$3"

  echo "Waiting for pods in namespace '$ns' with selector '$selector' to appear and become Ready..."

  local end=$((SECONDS + timeout_sec))

  # ждать пока появится хотя бы 1 pod
  while true; do
    local count
    count="$(kubectl -n "$ns" get pods -l "$selector" --no-headers 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "${count}" != "0" ]]; then
      break
    fi
    if (( SECONDS > end )); then
      echo "ERROR: timeout waiting for pods to be created (selector: $selector)"
      kubectl -n "$ns" get pods
      exit 1
    fi
    sleep 2
  done

  # ждать Ready
  kubectl -n "$ns" wait --for=condition=Ready pod -l "$selector" --timeout="${timeout_sec}s"
}

echo "== Namespaces =="
kubectl get ns infra >/dev/null 2>&1  kubectl create namespace infra
kubectl get ns lms >/dev/null 2>&1  kubectl create namespace lms

echo
echo "== Helm repos =="
helm repo add bitnami https://charts.bitnami.com/bitnami >/dev/null 2>&1  true
helm repo add minio https://charts.min.io/ >/dev/null 2>&1  true
helm repo update >/dev/null

echo
echo "== Install/Upgrade PostgreSQL (bitnami/postgresql) =="
helm upgrade --install postgres bitnami/postgresql -n infra \
  -f helm-values/postgres-values.yaml \
  --set auth.postgresPassword="${PG_POSTGRES_PASSWORD}" \
  --set auth.database="${PG_DATABASE}"

echo
echo "== Install/Upgrade MinIO (minio/minio) =="
# Важно: standalone + 1 replica (иначе на малой памяти MinIO попытается поднять много pod).
# Также отключаем hooks, чтобы не зависеть от post-job и таймаутов.
helm upgrade --install minio minio/minio -n infra \
  -f helm-values/minio-values.yaml \
  --set rootUser="${MINIO_ROOT_USER}" \
  --set rootPassword="${MINIO_ROOT_PASSWORD}" \
  --set persistence.size="${MINIO_PERSISTENCE_SIZE}" \
  --no-hooks

echo
echo "== Current pods (infra) =="
kubectl -n infra get pods

echo
echo "== Waiting for PostgreSQL pods Ready =="
wait_for_pods_by_label "infra" "app.kubernetes.io/instance=postgres,app.kubernetes.io/name=postgresql" 600

echo
echo "== Waiting for MinIO pods Ready =="
wait_for_pods_by_label "infra" "app.kubernetes.io/instance=minio,app.kubernetes.io/name=minio" 600

echo
echo "== Services (infra) =="
kubectl -n infra get svc

echo
echo "== MinIO endpoints =="
kubectl -n infra get endpoints minio -o wide || true

echo
echo "OK: infra installed."
