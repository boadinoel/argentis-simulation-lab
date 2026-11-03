# Upstream supplies the large OASIS/PyTorch dependency environment.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend ./frontend
COPY locales ./locales
RUN cd frontend && npm run build

FROM ghcr.io/666ghj/mirofish:latest
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen && uv pip install gunicorn==23.0.0
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
ENV PYTHONUNBUFFERED=1 FLASK_DEBUG=false
EXPOSE 3000
WORKDIR /app/backend
CMD [".venv/bin/gunicorn", "--bind", "[::]:3000", "--workers", "1", "--threads", "16", "--timeout", "0", "--graceful-timeout", "30", "lab_server:app"]
