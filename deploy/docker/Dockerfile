# Build the static workspace; no Node process is added to the runtime.
FROM node:22-slim AS frontend
WORKDIR /src
COPY package.json package-lock.json ./
COPY packages ./packages/
COPY apps/web ./apps/web/
COPY apps/admin/package.json ./apps/admin/package.json
COPY apps/docs/package.json ./apps/docs/package.json
RUN npm ci --no-audit --no-fund
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace @ago/web

# M10 pinned major/minor Python runtime; the final production rollout must pin base image digests.
FROM python:3.11-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src/apps/backend
COPY apps/backend/pyproject.toml ./
COPY apps/backend/ago ./ago/
COPY --from=frontend /src/apps/web/out ./ago/frontend/
COPY scripts/package_frontend.py /src/scripts/package_frontend.py
COPY --from=frontend /src/apps/web/out /src/apps/web/out/
RUN python /src/scripts/package_frontend.py
RUN python -m pip wheel --no-deps --wheel-dir=/wheels .

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AGO_ENVIRONMENT=production AGO_MIGRATIONS_DIR=/app/deploy/sql
RUN groupadd --gid 10001 ago && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin ago && \
    mkdir -p /app/deploy/sql /tmp && chown -R ago:ago /app /tmp
COPY --from=build /wheels /tmp/wheels
RUN python -m pip install --no-cache-dir '/tmp/wheels/'*.whl 'psycopg[binary]>=3.2,<4' 'fastembed==0.7.4' 'redis==6.4.0' && \
    rm -rf /tmp/wheels && \
    python -c 'from importlib.resources import files; p=files("ago").joinpath("console","index.html"); assert p.is_file(); assert files("ago").joinpath("frontend","index.html").is_file()'
COPY --chown=ago:ago deploy/sql/ /app/deploy/sql/
WORKDIR /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8000/health/live', timeout=3).status == 200"
# Trust no forwarded headers by default; production reverse proxy trust requires a reviewed override.
CMD ["uvicorn", "ago.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
