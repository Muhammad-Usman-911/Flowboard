# Flowboard API image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as a non-root user; uploads go to a folder it owns (mounted as a volume in compose).
RUN useradd --create-home --uid 1000 flowboard \
    && mkdir -p /app/uploads \
    && chown -R flowboard /app/uploads \
    && chmod +x /app/docker-entrypoint.sh
USER flowboard

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
