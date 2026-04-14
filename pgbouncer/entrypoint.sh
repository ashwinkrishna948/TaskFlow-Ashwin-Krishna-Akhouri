#!/bin/sh
set -e

POOL_SIZE="${PGBOUNCER_POOL_SIZE:-50}"
POSTGRES_DB="${POSTGRES_DB:-taskflow}"
POSTGRES_USER="${POSTGRES_USER:-taskflow}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

cat > /etc/pgbouncer/pgbouncer.ini << EOF
[databases]
${POSTGRES_DB} = host=${POSTGRES_HOST} port=${POSTGRES_PORT} dbname=${POSTGRES_DB}

[pgbouncer]
listen_addr             = 0.0.0.0
listen_port             = 5432
auth_type               = plain
auth_file               = /etc/pgbouncer/userlist.txt
pool_mode               = transaction
max_client_conn         = 10000
default_pool_size       = ${POOL_SIZE}
ignore_startup_parameters = extra_float_digits,options
server_reset_query      =
server_reset_query_always = 0
log_connections         = 0
log_disconnections      = 0
log_pooler_errors       = 1
server_idle_timeout     = 600
client_idle_timeout     = 0
EOF

echo "\"${POSTGRES_USER}\" \"${POSTGRES_PASSWORD}\"" > /etc/pgbouncer/userlist.txt

echo ">>> PgBouncer config written. Pool size: ${POOL_SIZE}"
exec /opt/pgbouncer/pgbouncer /etc/pgbouncer/pgbouncer.ini
