# ---- Stage 1: build --------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client \
        curl \
    && curl -fsSL \
        -o /usr/local/bin/dbmate \
        https://github.com/amacneil/dbmate/releases/download/v2.20.0/dbmate-linux-amd64 \
    && chmod +x /usr/local/bin/dbmate \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
