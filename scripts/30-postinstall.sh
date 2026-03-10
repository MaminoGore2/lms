#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "== Detecting PostgreSQL pod =="
PG_POD="$(kubectl -n infra get pod \
  -l app.kubernetes.io/instance=postgres,app.kubernetes.io/name=postgresql \
  -o jsonpath='{.items[0].metadata.name}')"
echo "PostgreSQL pod: $PG_POD"

echo
echo "== Checking MinIO endpoints =="
kubectl -n infra get endpoints minio -o wide

echo
echo "== PostgreSQL: create app user (idempotent) =="
kubectl -n infra exec -i "$PG_POD" -- bash -lc \
"export PGPASSWORD='${PG_POSTGRES_PASSWORD}';
psql -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c \"
DO \\\$\\\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${PG_APP_USER}') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '${PG_APP_USER}', '${PG_APP_PASSWORD}');
  END IF;
END
\\\$\\\$;\""

echo
echo "== PostgreSQL: grant privileges on database =="
kubectl -n infra exec -i "$PG_POD" -- bash -lc \
"export PGPASSWORD='${PG_POSTGRES_PASSWORD}';
psql -h 127.0.0.1 -U postgres -d postgres -v ON_ERROR_STOP=1 -c \"
ALTER DATABASE ${PG_DATABASE} OWNER TO ${PG_APP_USER};
GRANT ALL PRIVILEGES ON DATABASE ${PG_DATABASE} TO ${PG_APP_USER};
\""

echo
echo "== PostgreSQL: schema/public permissions + default privileges =="
kubectl -n infra exec -i "$PG_POD" -- bash -lc \
"export PGPASSWORD='${PG_POSTGRES_PASSWORD}';
psql -h 127.0.0.1 -U postgres -d '${PG_DATABASE}' -v ON_ERROR_STOP=1 -c \"
GRANT USAGE, CREATE ON SCHEMA public TO ${PG_APP_USER};
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${PG_APP_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN
