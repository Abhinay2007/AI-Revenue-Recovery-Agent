FROM node:22-alpine AS frontend-build

WORKDIR /frontend

ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/package.json frontend/bun.lock ./
RUN npm install --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATASET_PATH=/app/data/generated/orders.csv \
    ARTIFACT_PATH=/app/data/generated/models/rto_predictor.joblib

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y nginx nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
RUN pip install --no-cache-dir /app/backend

COPY data /app/data
COPY --from=frontend-build /frontend/.output /app/frontend/.output
COPY docker/hf-nginx.conf /etc/nginx/nginx.conf.template
COPY docker/hf-entrypoint.sh /app/hf-entrypoint.sh
RUN chmod +x /app/hf-entrypoint.sh

CMD ["/app/hf-entrypoint.sh"]
