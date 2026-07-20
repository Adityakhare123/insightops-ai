import {
  useState,
  type FormEvent,
} from "react";

import { ApiError } from "../../api/client";
import { useAuth } from "./AuthContext";


interface LoginFormState {
  workspaceSlug: string;
  email: string;
  password: string;
}


const INITIAL_FORM_STATE: LoginFormState = {
  workspaceSlug: "insightops-insurance-demo",
  email: "admin@insightops.ai",
  password: "",
};


function getLoginErrorMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Unable to sign in. Please try again.";
}


export default function LoginPage() {
  const { login } = useAuth();

  const [formState, setFormState] =
    useState<LoginFormState>(
      INITIAL_FORM_STATE,
    );

  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] =
    useState(false);


  function updateField(
    field: keyof LoginFormState,
    value: string,
  ): void {
    setFormState((currentState) => ({
      ...currentState,
      [field]: value,
    }));
  }


  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (isSubmitting) {
      return;
    }

    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await login({
        workspace_slug:
          formState.workspaceSlug.trim(),
        email: formState.email.trim(),
        password: formState.password,
      });
    } catch (error) {
      setErrorMessage(
        getLoginErrorMessage(error),
      );
    } finally {
      setIsSubmitting(false);
    }
  }


  return (
    <main className="login-page">
      <section className="login-introduction">
        <div className="brand-mark">
          <span>IO</span>
        </div>

        <p className="eyebrow">
          Agentic operations intelligence
        </p>

        <h1>
          Turn operational data into decisions.
        </h1>

        <p className="login-description">
          Reconcile policies, payments, commissions,
          and business documents with AI-assisted
          analytics and auditable workflows.
        </p>

        <div className="login-feature-grid">
          <article>
            <span>01</span>
            <h2>Document intelligence</h2>
            <p>
              Extract, validate, and organize
              operational documents.
            </p>
          </article>

          <article>
            <span>02</span>
            <h2>Agentic analysis</h2>
            <p>
              Investigate discrepancies using
              controlled AI agents.
            </p>
          </article>

          <article>
            <span>03</span>
            <h2>Business reporting</h2>
            <p>
              Generate traceable answers, reports,
              and downloadable results.
            </p>
          </article>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="login-card-header">
            <p className="eyebrow">
              Secure workspace
            </p>

            <h2>Sign in to InsightOps</h2>

            <p>
              Enter your workspace and administrator
              credentials to continue.
            </p>
          </div>

          <form
            className="login-form"
            onSubmit={handleSubmit}
          >
            <label htmlFor="workspace-slug">
              <span>Workspace</span>

              <input
                id="workspace-slug"
                name="workspace_slug"
                type="text"
                value={formState.workspaceSlug}
                onChange={(event) => {
                  updateField(
                    "workspaceSlug",
                    event.target.value,
                  );
                }}
                autoComplete="organization"
                required
                disabled={isSubmitting}
              />
            </label>

            <label htmlFor="email">
              <span>Email address</span>

              <input
                id="email"
                name="email"
                type="email"
                value={formState.email}
                onChange={(event) => {
                  updateField(
                    "email",
                    event.target.value,
                  );
                }}
                autoComplete="email"
                required
                disabled={isSubmitting}
              />
            </label>

            <label htmlFor="password">
              <span>Password</span>

              <input
                id="password"
                name="password"
                type="password"
                value={formState.password}
                onChange={(event) => {
                  updateField(
                    "password",
                    event.target.value,
                  );
                }}
                autoComplete="current-password"
                placeholder="Enter your password"
                required
                disabled={isSubmitting}
              />
            </label>

            {errorMessage && (
              <div
                className="login-error"
                role="alert"
              >
                {errorMessage}
              </div>
            )}

            <button
              className="login-submit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Authenticating…"
                : "Continue to workspace"}
            </button>
          </form>

          <div className="demo-account-note">
            <span>Demo account</span>

            <strong>
              admin@insightops.ai
            </strong>

            <p>
              The password is loaded from your local
              DEMO_ADMIN_PASSWORD setting.
            </p>
          </div>
        </div>

        <p className="login-footer">
          InsightOps AI · Secure operations workspace
        </p>
      </section>
    </main>
  );
}