import {
  useState,
} from "react";

import {
  useQuery,
} from "@tanstack/react-query";

import { apiClient } from "../../api/client";
import { useAuth } from "../auth/AuthContext";
import DocumentsWorkspace from "../documents/DocumentsWorkspace";
import UploadDocumentModal from "../documents/UploadDocumentModal";
import RAGWorkspace from "../rag/RAGWorkspace";

import type {
  HealthResponse,
} from "../../types/health";


type DashboardSection =
  | "overview"
  | "documents"
  | "rag";


interface DashboardMetric {
  label: string;
  value: string;
  change: string;
  status: "positive" | "warning" | "neutral";
}


const DASHBOARD_METRICS: DashboardMetric[] = [
  {
    label: "Policies monitored",
    value: "150",
    change: "5 duplicate records detected",
    status: "warning",
  },
  {
    label: "Payments matched",
    value: "85",
    change: "8 active policies need review",
    status: "warning",
  },
  {
    label: "Commission records",
    value: "85",
    change: "Reconciliation dataset ready",
    status: "positive",
  },
  {
    label: "Documents uploaded",
    value: "0",
    change: "Upload workflow is now active",
    status: "neutral",
  },
];


async function fetchHealth():
Promise<HealthResponse> {
  return apiClient.get<HealthResponse>(
    "/health",
    {
      auth: false,
      retryOnUnauthorized: false,
    },
  );
}


function getInitials(
  fullName: string,
): string {
  return fullName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map(
      (namePart) =>
        namePart[0]?.toUpperCase(),
    )
    .join("");
}


export default function DashboardPage() {
  const {
    user,
    workspaceName,
    workspaceSlug,
    logout,
  } = useAuth();

  const [
    activeSection,
    setActiveSection,
  ] = useState<DashboardSection>(
    "overview",
  );

  const [
    isUploadModalOpen,
    setIsUploadModalOpen,
  ] = useState(false);

  const healthQuery = useQuery({
    queryKey: ["api-health"],
    queryFn: fetchHealth,
    retry: 1,
    refetchInterval: 60_000,
  });

  if (!user) {
    return null;
  }

  const currentDate =
    new Intl.DateTimeFormat(
      "en",
      {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      },
    ).format(new Date());

  return (
    <div className="dashboard-layout">
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark">
            IO
          </div>

          <div>
            <strong>InsightOps</strong>

            <span>
              Operations intelligence
            </span>
          </div>
        </div>

        <nav
          className="sidebar-navigation"
          aria-label="Primary navigation"
        >
          <p>Workspace</p>

          <button
            className={
              activeSection === "overview"
                ? "sidebar-navigation-item active"
                : "sidebar-navigation-item"
            }
            type="button"
            onClick={() => {
              setActiveSection("overview");
            }}
          >
            <span>01</span>
            Overview
          </button>

          <button
            className={
              activeSection === "documents"
                ? "sidebar-navigation-item active"
                : "sidebar-navigation-item"
            }
            type="button"
            onClick={() => {
              setActiveSection("documents");
            }}
          >
            <span>02</span>
            Documents
          </button>

          <button
            className={
              activeSection === "rag"
                ? "sidebar-navigation-item active"
                : "sidebar-navigation-item"
            }
            type="button"
            onClick={() => {
              setActiveSection("rag");
            }}
          >
            <span>03</span>
            Ask InsightOps
          </button>

          <button
            className="sidebar-navigation-item"
            type="button"
          >
            <span>04</span>
            Reconciliation
          </button>

          <button
            className="sidebar-navigation-item"
            type="button"
          >
            <span>05</span>
            Reports
          </button>

          <p>Administration</p>

          <button
            className="sidebar-navigation-item"
            type="button"
          >
            <span>06</span>
            Data sources
          </button>

          <button
            className="sidebar-navigation-item"
            type="button"
          >
            <span>07</span>
            Users and access
          </button>

          <button
            className="sidebar-navigation-item"
            type="button"
          >
            <span>08</span>
            System health
          </button>
        </nav>

        <div className="sidebar-user">
          <div className="sidebar-user-avatar">
            {getInitials(user.full_name)}
          </div>

          <div className="sidebar-user-details">
            <strong>
              {user.full_name}
            </strong>

            <span>
              {user.role.replaceAll(
                "_",
                " ",
              )}
            </span>
          </div>

          <button
            className="sidebar-logout"
            type="button"
            onClick={logout}
            aria-label="Sign out"
            title="Sign out"
          >
            {"->"}
          </button>
        </div>
      </aside>

      <main className="dashboard-main">
        {activeSection === "overview" && (
          <>
            <header className="dashboard-header">
              <div>
                <p className="dashboard-date">
                  {currentDate}
                </p>

                <h1>
                  Good to see you,{" "}
                  {
                    user.full_name
                      .split(" ")[0]
                  }.
                </h1>

                <p>
                  Monitor operational data,
                  investigate discrepancies,
                  and generate auditable
                  intelligence.
                </p>
              </div>

              <div className="dashboard-header-actions">
                <div className="environment-status">
                  <span
                    className={
                      healthQuery.data?.status
                        === "healthy"
                        ? (
                          "environment-status-dot "
                          + "healthy"
                        )
                        : "environment-status-dot"
                    }
                  />

                  <div>
                    <strong>
                      {
                        healthQuery.isPending
                          ? "Checking services"
                          : healthQuery.isError
                            ? "API unavailable"
                            : "Systems operational"
                      }
                    </strong>

                    <span>
                      {
                        healthQuery.data
                          ? (
                            `API v${
                              healthQuery.data.version
                            }`
                          )
                          : "Backend connection"
                      }
                    </span>
                  </div>
                </div>

                <button
                  className={
                    "dashboard-primary-action"
                  }
                  type="button"
                  onClick={() => {
                    setIsUploadModalOpen(true);
                  }}
                >
                  Upload document
                </button>
              </div>
            </header>

            <section className="workspace-summary">
              <div>
                <span>
                  Current workspace
                </span>

                <strong>
                  {
                    workspaceName
                    ?? "InsightOps Workspace"
                  }
                </strong>
              </div>

              <div>
                <span>Workspace ID</span>

                <strong>
                  {
                    workspaceSlug
                    ?? "Not available"
                  }
                </strong>
              </div>

              <div>
                <span>Access level</span>

                <strong>
                  {
                    user.role.replaceAll(
                      "_",
                      " ",
                    )
                  }
                </strong>
              </div>
            </section>

            <section className="dashboard-metrics">
              {DASHBOARD_METRICS.map(
                (metric) => (
                  <article
                    className={
                      "dashboard-metric-card"
                    }
                    key={metric.label}
                  >
                    <div
                      className={
                        "dashboard-metric-header"
                      }
                    >
                      <span>
                        {metric.label}
                      </span>

                      <span
                        className={
                          `metric-indicator ${
                            metric.status
                          }`
                        }
                      />
                    </div>

                    <strong>
                      {metric.value}
                    </strong>

                    <p>
                      {metric.change}
                    </p>
                  </article>
                ),
              )}
            </section>

            <section className="dashboard-content-grid">
              <article
                className={
                  "dashboard-panel "
                  + "operational-panel"
                }
              >
                <div
                  className={
                    "dashboard-panel-header"
                  }
                >
                  <div>
                    <p
                      className={
                        "dashboard-panel-label"
                      }
                    >
                      Reconciliation overview
                    </p>

                    <h2>
                      Operational exceptions
                    </h2>
                  </div>

                  <button type="button">
                    View all
                  </button>
                </div>

                <div className="exception-list">
                  <div className="exception-item">
                    <span
                      className={
                        "exception-number"
                      }
                    >
                      08
                    </span>

                    <div>
                      <strong>
                        Active policies without
                        payments
                      </strong>

                      <p>
                        Intentional validation
                        cases ready for
                        investigation.
                      </p>
                    </div>

                    <span
                      className={
                        "exception-badge warning"
                      }
                    >
                      Review
                    </span>
                  </div>

                  <div className="exception-item">
                    <span
                      className={
                        "exception-number"
                      }
                    >
                      05
                    </span>

                    <div>
                      <strong>
                        Duplicate policy numbers
                      </strong>

                      <p>
                        Matching business
                        identifiers exist across
                        source records.
                      </p>
                    </div>

                    <span
                      className={
                        "exception-badge warning"
                      }
                    >
                      Review
                    </span>
                  </div>

                  <div className="exception-item">
                    <span
                      className={
                        "exception-number"
                      }
                    >
                      85
                    </span>

                    <div>
                      <strong>
                        Commissions linked
                        successfully
                      </strong>

                      <p>
                        Every generated payment
                        has a corresponding
                        commission record.
                      </p>
                    </div>

                    <span
                      className={
                        "exception-badge positive"
                      }
                    >
                      Matched
                    </span>
                  </div>
                </div>
              </article>

              <article
                className={
                  "dashboard-panel "
                  + "activity-panel"
                }
              >
                <div
                  className={
                    "dashboard-panel-header"
                  }
                >
                  <div>
                    <p
                      className={
                        "dashboard-panel-label"
                      }
                    >
                      Platform status
                    </p>

                    <h2>
                      Build progress
                    </h2>
                  </div>
                </div>

                <div className="build-progress">
                  <div
                    className={
                      "build-progress-header"
                    }
                  >
                    <strong>60%</strong>

                    <span>
                      6 of 10 days
                    </span>
                  </div>

                  <div
                    className={
                      "build-progress-track"
                    }
                  >
                    <span
                      style={{
                        width: "60%",
                      }}
                    />
                  </div>
                </div>

                <div className="activity-timeline">
                  <div
                    className={
                      "activity-entry complete"
                    }
                  >
                    <span />

                    <div>
                      <strong>
                        Platform foundation
                      </strong>

                      <p>
                        Docker services and
                        health checks configured.
                      </p>
                    </div>
                  </div>

                  <div
                    className={
                      "activity-entry complete"
                    }
                  >
                    <span />

                    <div>
                      <strong>
                        Insurance data model
                      </strong>

                      <p>
                        Synthetic operational
                        dataset seeded.
                      </p>
                    </div>
                  </div>

                  <div
                    className={
                      "activity-entry complete"
                    }
                  >
                    <span />

                    <div>
                      <strong>
                        Authentication
                      </strong>

                      <p>
                        Secure login and
                        protected workspace
                        active.
                      </p>
                    </div>
                  </div>

                  <div
                    className={
                      "activity-entry complete"
                    }
                  >
                    <span />

                    <div>
                      <strong>
                        Document intelligence
                      </strong>

                      <p>
                        Extraction, chunking,
                        embeddings, and grounded
                        document Q&amp;A are active.
                      </p>
                    </div>
                  </div>

                  <div
                    className={
                      "activity-entry current"
                    }
                  >
                    <span />

                    <div>
                      <strong>
                        Agentic intelligence
                      </strong>

                      <p>
                        Safe SQL and reconciliation
                        agents are the next phase.
                      </p>
                    </div>
                  </div>
                </div>
              </article>
            </section>
          </>
        )}

        {activeSection === "documents" && (
          <DocumentsWorkspace
            onUploadClick={() => {
              setIsUploadModalOpen(true);
            }}
          />
        )}

        {activeSection === "rag" && (
          <RAGWorkspace />
        )}
      </main>

      <UploadDocumentModal
        isOpen={isUploadModalOpen}
        onClose={() => {
          setIsUploadModalOpen(false);
        }}
        onUploaded={() => {
          setActiveSection("documents");
        }}
      />
    </div>
  );
}