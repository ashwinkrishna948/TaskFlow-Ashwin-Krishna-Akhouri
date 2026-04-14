FROM pgbouncer/pgbouncer:latest
# COPY --chmod sets permissions at build time (BuildKit).
# The base image has a read-only root filesystem, so RUN chmod fails.
COPY --chmod=755 entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
