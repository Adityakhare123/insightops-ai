# InsightOps AI

Agentic Business Intelligence and Document Intelligence Platform.

## Current status

Day 1 foundation scaffold.

## Services

- React + TypeScript frontend
- FastAPI backend
- PostgreSQL with pgvector
- Redis
- Celery worker
- MinIO object storage

## Start locally

1. Copy the environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Update secrets in `.env`.

3. Start the stack:

```bash
docker compose up --build
```

## Local URLs

- Frontend: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health endpoint: http://localhost:8000/api/v1/health
- MinIO console: http://localhost:9001

## Current flow

```text
Browser
  -> React frontend
  -> FastAPI health endpoint
  -> PostgreSQL/Redis/MinIO services available
  -> Celery worker ready for future document jobs
```

## Repository layout

See `docs/folder-structure.md`.

## Development status

- [x] Monorepo scaffold
- [x] Docker Compose
- [x] FastAPI application
- [x] Health endpoint
- [x] React shell
- [x] Celery worker
- [ ] Authentication
- [ ] Database models
- [ ] Document upload
- [ ] OCR
- [ ] RAG
- [ ] SQL Agent
