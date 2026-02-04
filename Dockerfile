FROM node:20-slim AS frontend-builder

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

FROM python:3.12-slim

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/worldlines /usr/local/bin/worldlines
COPY --from=builder /usr/local/bin/worldlines-web /usr/local/bin/worldlines-web
COPY --from=frontend-builder /build/dist /app/static/
COPY src/ /app/src/
COPY config/ /app/config/

RUN mkdir -p /data && \
    useradd --system --no-create-home appuser && \
    chown appuser:appuser /data

USER appuser
WORKDIR /app

CMD ["worldlines"]
