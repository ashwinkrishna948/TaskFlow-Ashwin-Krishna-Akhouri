#!/bin/sh
set -e

echo ">>> Waiting for Postgres at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until pg_isready -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -q; do
    sleep 1
done
echo ">>> Postgres is ready."

echo ">>> Running migrations..."
dbmate --url "${DATABASE_URL}" --migrations-dir /app/db/migrations up
echo ">>> Migrations done."

echo ">>> Running seed script..."
python /app/db/seed.py
echo ">>> Seed done."

if [ -n "${AZURE_KEYVAULT_URL}" ] && [ -n "${JWT_SECRET}" ]; then
    MINIBLUE_HEALTH=$(echo "${AZURE_KEYVAULT_URL}" | sed 's|/keyvault/.*||')/health
    echo ">>> Waiting for miniblue at ${MINIBLUE_HEALTH}..."
    until curl -sf "${MINIBLUE_HEALTH}" > /dev/null 2>&1; do
        sleep 1
    done
    echo ">>> miniblue is ready."

    echo ">>> Seeding Azure Key Vault at ${AZURE_KEYVAULT_URL}..."
    curl -sf -X PUT "${AZURE_KEYVAULT_URL}/secrets/jwt-secret" \
        -H "Content-Type: application/json" \
        -d "{\"value\": \"${JWT_SECRET}\"}" > /dev/null \
    && echo ">>> jwt-secret written to vault." \
    || echo ">>> Warning: vault seed failed — falling back to JWT_SECRET env var."
fi

echo ">>> Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level warning
