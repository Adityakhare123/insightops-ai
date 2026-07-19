---
project: InsightOps AI
document: Folder Structure
status: Active
created: 2026-07-17
tags:
  - insightops-ai
  - architecture
  - folder-structure
---

# InsightOps AI — Folder Structure

```text
insightops-ai/
├── apps/
│   ├── api/                    # FastAPI application
│   │   ├── app/
│   │   │   ├── api/v1/        # Versioned API endpoints
│   │   │   ├── core/          # Configuration and security
│   │   │   ├── db/            # Database models and repositories
│   │   │   ├── schemas/       # Pydantic request/response models
│   │   │   ├── services/      # Business services
│   │   │   ├── middleware/    # Request middleware
│   │   │   └── main.py        # FastAPI entry point
│   │   └── Dockerfile
│   │
│   └── frontend/               # React + TypeScript application
│       ├── src/
│       │   ├── api/
│       │   ├── components/
│       │   ├── features/
│       │   ├── layouts/
│       │   ├── pages/
│       │   ├── routes/
│       │   ├── types/
│       │   └── utils/
│       └── Dockerfile
│
├── workers/                    # Celery background tasks
├── packages/
│   ├── agents/                 # Agent graph and specialized agents
│   ├── document_intelligence/  # OCR and extraction
│   ├── rag/                    # Retrieval and citations
│   ├── sql_intelligence/       # Safe text-to-SQL
│   ├── data_engineering/       # Cleaning and ETL
│   ├── reporting/              # CSV, Excel, PDF
│   └── shared/                 # Shared types and utilities
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
├── data/
├── docs/
├── project-status/
├── infrastructure/
├── .github/workflows/
├── docker-compose.yml
├── pyproject.toml
├── Makefile
└── README.md
```

## Why this structure exists

The project uses clear boundaries:

- `apps` contains deployable user-facing applications.
- `workers` contains asynchronous execution.
- `packages` contains reusable domain logic.
- `tests` mirrors system responsibilities.
- `docs` records architectural and business decisions.
- `infrastructure` contains deployment configuration.

This prevents OCR, RAG, API routes, database access, and agents from becoming mixed inside one large Python file.
