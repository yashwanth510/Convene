FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir . && useradd --create-home convene && mkdir -p /app/data && chown -R convene:convene /app
USER convene
EXPOSE 8001
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1 --timeout-graceful-shutdown 25"]
