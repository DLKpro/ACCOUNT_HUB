# Stage 1: Build frontend
FROM node:22-slim AS frontend
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

# Stage 2: Python API + serve built frontend
FROM python:3.12-slim
WORKDIR /app
COPY . .
COPY --from=frontend /web/dist ./web/dist
RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD uvicorn account_hub.api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}
