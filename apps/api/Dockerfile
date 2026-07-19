FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip     && pip install --no-cache-dir -e ".[dev]"

COPY apps /app/apps
COPY packages /app/packages
COPY workers /app/workers
COPY tests /app/tests

EXPOSE 8000
