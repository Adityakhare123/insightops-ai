import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./api/client";
import type { HealthResponse } from "./types/health";

async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>("/health");
  return response.data;
}

export default function App() {
  const healthQuery = useQuery({
    queryKey: ["api-health"],
    queryFn: fetchHealth,
    retry: 1,
  });

  return (
    <main className="app-shell">
      <section className="hero-card">
        <p className="eyebrow">Day 1 Foundation</p>
        <h1>InsightOps AI</h1>
        <p className="subtitle">
          Agentic Business Intelligence and Document Intelligence Platform
        </p>

        <div className="status-panel">
          <span>Backend status</span>
          {healthQuery.isPending && <strong>Checking…</strong>}
          {healthQuery.isError && <strong>Unavailable</strong>}
          {healthQuery.data && (
            <strong>
              {healthQuery.data.status} · v{healthQuery.data.version}
            </strong>
          )}
        </div>

        <div className="next-step">
          <h2>Current foundation</h2>
          <ul>
            <li>React frontend</li>
            <li>FastAPI backend</li>
            <li>PostgreSQL with pgvector</li>
            <li>Redis and Celery worker</li>
            <li>MinIO object storage</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
