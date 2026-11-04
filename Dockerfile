# Single image: builds the React app, then serves it and the API from Django.

# ---- 1. Frontend build
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. Runtime
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DEBUG=False
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && useradd --create-home --uid 10001 app && chown -R app /app
USER app
EXPOSE 8000
# One process keeps the in-memory cache and the Valhalla 1 req/s throttle shared;
# threads give concurrency (requests are I/O-bound).
CMD gunicorn project_root.wsgi:application --bind 0.0.0.0:${PORT} \
    --workers 1 --threads 8 --timeout 90 --access-logfile -
