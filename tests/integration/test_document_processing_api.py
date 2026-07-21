from __future__ import annotations

import time
from uuid import UUID, uuid4

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.app.db.models.document import Document
from apps.api.app.db.models.user import User
from apps.api.app.db.models.workspace import Workspace
from apps.api.app.db.session import SessionLocal
from apps.api.app.main import app
from apps.api.app.services.storage import (
    StorageError,
    delete_object,
)


WORKSPACE_SLUG = "insightops-insurance-demo"
TEST_PASSWORD = "StrongPassword123!"

PROCESSING_TIMEOUT_SECONDS = 60
PROCESSING_POLL_INTERVAL_SECONDS = 1


def create_selectable_test_pdf() -> bytes:
    """Create a valid one-page PDF containing selectable text."""

    pdf_document = pymupdf.open()

    try:
        page = pdf_document.new_page()

        page.insert_text(
            (72, 72),
            "InsightOps Insurance Processing Test",
            fontsize=14,
        )

        page.insert_text(
            (72, 100),
            "Policy Number: POL-ASYNC-2026",
            fontsize=12,
        )

        page.insert_text(
            (72, 128),
            "Customer: Jane Doe",
            fontsize=12,
        )

        return pdf_document.tobytes()
    finally:
        pdf_document.close()


def get_demo_workspace_id() -> UUID:
    """Return the seeded demo workspace ID."""

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug == WORKSPACE_SLUG
            )
        )

    assert workspace_id is not None, (
        "The demo workspace is missing. Run the demo seed "
        "script before running this integration test."
    )

    return workspace_id


def cleanup_test_user(
    *,
    workspace_id: UUID,
    email: str,
) -> None:
    """
    Remove test documents, MinIO objects, and the test user.

    Database cascades remove processing runs and document pages.
    """

    with SessionLocal() as database_session:
        user = database_session.scalar(
            select(User).where(
                User.workspace_id == workspace_id,
                User.email == email,
            )
        )

        if user is None:
            return

        documents = list(
            database_session.scalars(
                select(Document).where(
                    Document.workspace_id == workspace_id,
                    Document.uploaded_by_user_id == user.id,
                )
            ).all()
        )

        for document in documents:
            try:
                delete_object(
                    bucket_name=document.storage_bucket,
                    object_name=document.storage_object_name,
                )
            except StorageError:
                pass

            database_session.delete(document)

        database_session.flush()
        database_session.delete(user)
        database_session.commit()


def wait_for_processing_completion(
    *,
    client: TestClient,
    headers: dict[str, str],
    document_id: str,
) -> dict[str, object]:
    """Poll processing runs until the newest run completes or fails."""

    deadline = (
        time.monotonic()
        + PROCESSING_TIMEOUT_SECONDS
    )

    latest_run: dict[str, object] | None = None

    while time.monotonic() < deadline:
        response = client.get(
            (
                f"/api/v1/documents/"
                f"{document_id}/processing-runs"
            ),
            headers=headers,
            params={
                "limit": 20,
                "offset": 0,
            },
        )

        assert response.status_code == 200, (
            response.text
        )

        response_data = response.json()
        processing_runs = response_data["items"]

        if processing_runs:
            latest_run = processing_runs[0]
            run_status = latest_run["status"]

            if run_status == "completed":
                return latest_run

            if run_status == "failed":
                raise AssertionError(
                    "Document processing failed: "
                    f"{latest_run.get('error_message')}"
                )

        time.sleep(
            PROCESSING_POLL_INTERVAL_SECONDS
        )

    raise AssertionError(
        "Document processing did not complete within "
        f"{PROCESSING_TIMEOUT_SECONDS} seconds. "
        f"Latest run: {latest_run}"
    )


def test_complete_asynchronous_document_processing_flow() -> None:
    workspace_id = get_demo_workspace_id()

    unique_identifier = uuid4().hex[:12]

    test_email = (
        f"processing-test-{unique_identifier}@example.com"
    )

    test_filename = (
        f"processing-test-{unique_identifier}.pdf"
    )

    pdf_data = create_selectable_test_pdf()

    cleanup_test_user(
        workspace_id=workspace_id,
        email=test_email,
    )

    try:
        with TestClient(app) as client:
            registration_response = client.post(
                "/api/v1/auth/register",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "full_name": (
                        "Document Processing Test User"
                    ),
                    "password": TEST_PASSWORD,
                },
            )

            assert (
                registration_response.status_code
                == 201
            ), registration_response.text

            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "password": TEST_PASSWORD,
                },
            )

            assert (
                login_response.status_code
                == 200
            ), login_response.text

            login_data = login_response.json()

            authorization_headers = {
                "Authorization": (
                    f"Bearer {login_data['access_token']}"
                )
            }

            upload_response = client.post(
                "/api/v1/documents/upload",
                headers=authorization_headers,
                files={
                    "file": (
                        test_filename,
                        pdf_data,
                        "application/pdf",
                    )
                },
            )

            assert (
                upload_response.status_code
                == 201
            ), upload_response.text

            uploaded_document = (
                upload_response.json()["document"]
            )

            document_id = uploaded_document["id"]

            assert (
                uploaded_document["status"]
                == "uploaded"
            )

            queue_response = client.post(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/process"
                ),
                headers=authorization_headers,
                params={
                    "ocr_language": "eng",
                },
            )

            assert (
                queue_response.status_code
                == 202
            ), queue_response.text

            queue_data = queue_response.json()
            queued_run = queue_data["processing_run"]

            assert queue_data["message"] == (
                "Document processing queued successfully."
            )

            assert queue_data["task_id"]
            assert queued_run["document_id"] == document_id
            assert queued_run["attempt_number"] == 1
            assert queued_run["status"] == "queued"

            duplicate_queue_response = client.post(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/process"
                ),
                headers=authorization_headers,
            )

            assert (
                duplicate_queue_response.status_code
                == 409
            )

            completed_run = (
                wait_for_processing_completion(
                    client=client,
                    headers=authorization_headers,
                    document_id=document_id,
                )
            )

            assert completed_run["status"] == "completed"
            assert completed_run["total_pages"] == 1
            assert completed_run["extracted_pages"] == 1
            assert completed_run["error_message"] is None
            assert completed_run["started_at"] is not None
            assert completed_run["completed_at"] is not None

            processing_run_id = completed_run["id"]

            pages_response = client.get(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/pages"
                ),
                headers=authorization_headers,
            )

            assert (
                pages_response.status_code
                == 200
            ), pages_response.text

            pages_data = pages_response.json()

            assert (
                pages_data["processing_run_id"]
                == processing_run_id
            )

            assert pages_data["total"] == 1
            assert len(pages_data["items"]) == 1

            extracted_page = pages_data["items"][0]

            assert extracted_page["page_number"] == 1
            assert extracted_page["status"] == "completed"
            assert extracted_page["extraction_method"] == (
                "pdf_native_text"
            )

            extracted_text = (
                extracted_page["text_content"]
            )

            assert (
                "InsightOps Insurance Processing Test"
                in extracted_text
            )

            assert (
                "Policy Number: POL-ASYNC-2026"
                in extracted_text
            )

            assert (
                "Customer: Jane Doe"
                in extracted_text
            )

            assert (
                extracted_page["confidence_score"]
                == 1.0
            )

            assert (
                extracted_page["character_count"]
                > 0
            )

            assert extracted_page["word_count"] > 0

            explicit_pages_response = client.get(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/pages"
                ),
                headers=authorization_headers,
                params={
                    "processing_run_id": (
                        processing_run_id
                    ),
                },
            )

            assert (
                explicit_pages_response.status_code
                == 200
            )

            assert (
                explicit_pages_response.json()["total"]
                == 1
            )

            document_response = client.get(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert (
                document_response.status_code
                == 200
            )

            processed_document = (
                document_response.json()
            )

            assert (
                processed_document["status"]
                == "processed"
            )

            assert (
                processed_document["page_count"]
                == 1
            )

            assert (
                processed_document["processing_error"]
                is None
            )

            latest_extraction = (
                processed_document[
                    "extra_metadata"
                ]["latest_extraction"]
            )

            assert (
                latest_extraction["processing_run_id"]
                == processing_run_id
            )

            assert (
                latest_extraction["attempt_number"]
                == 1
            )

            assert (
                latest_extraction["total_pages"]
                == 1
            )

            delete_response = client.delete(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert (
                delete_response.status_code
                == 200
            ), delete_response.text

            assert (
                delete_response.json()["document_id"]
                == document_id
            )

            deleted_document_response = client.get(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert (
                deleted_document_response.status_code
                == 404
            )

    finally:
        cleanup_test_user(
            workspace_id=workspace_id,
            email=test_email,
        )