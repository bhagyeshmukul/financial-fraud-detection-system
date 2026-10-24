# Build the non-root Python API image. Models/reports arrive as read-only deployment mounts.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# XGBoost needs Linux OpenMP for compiled tree code.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Run serving under a dedicated unprivileged identity.
RUN useradd --create-home --uid 10001 fraud
# Copy code; complete data/model artifacts arrive through deployment mounts.
COPY --chown=fraud:fraud app ./app
COPY --chown=fraud:fraud src ./src
COPY --chown=fraud:fraud alembic ./alembic
COPY --chown=fraud:fraud alembic.ini entrypoint.sh ./
RUN chmod +x entrypoint.sh && mkdir -p models/v2 reports/v2 data/raw && chown -R fraud:fraud /app
USER fraud
EXPOSE 8000
CMD ["/app/entrypoint.sh"]
