from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from apps.api.app.db.models.document import Document
from apps.api.app.db.models.user import User
from apps.api.app.db.models.workspace import Workspace
from apps.api.app.db.session import SessionLocal
from apps.api.app.main import app
from apps.api.app.services.storage import (
    StorageError,
    delete_object,
    object_exists,
)


WORKSPACE_SLUG = "insightops-insurance-demo"
TEST_PASSWORD = "StrongPassword123!"


def _assert_demo_workspace_exists() -> None:
    """Confirm that the Day 2 demo workspace is available."""

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug == WORKSPACE_SLUG
            )
        )

    assert workspace_id is not None, (
        "The demo workspace is missing. Run "
        "'python -m scripts.seed_demo_data' first."
    )


def _cleanup_test_user(email: str) -> None:
    """
    Remove documents, storage objects, and the test user.

    This cleanup also runs when the integration test fails.
    """

    with SessionLocal() as database_session:
        workspace_id = database_session.scalar(
            select(Workspace.id).where(
                Workspace.slug == WORKSPACE_SLUG
            )
        )

        if workspace_id is None:
            return

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

        database_session.execute(
            delete(Document).where(
                Document.workspace_id == workspace_id,
                Document.uploaded_by_user_id == user.id,
            )
        )

        database_session.delete(user)
        database_session.commit()


def test_complete_document_upload_flow() -> None:
    _assert_demo_workspace_exists()

    unique_identifier = uuid4().hex[:12]

    test_email = (
        f"document-test-{unique_identifier}@example.com"
    )

    test_filename = (
        f"policy-report-{unique_identifier}.pdf"
    )

    pdf_data = (
        b"%PDF-1.7\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog >>\n"
        b"endobj\n"
        b"trailer\n"
        b"<< /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    expected_checksum = hashlib.sha256(
        pdf_data
    ).hexdigest()

    _cleanup_test_user(test_email)

    try:
        with TestClient(app) as client:
            registration_response = client.post(
                "/api/v1/auth/register",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "full_name": "Document Test User",
                    "password": TEST_PASSWORD,
                },
            )

            assert (
                registration_response.status_code
                == 201
            )

            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug": WORKSPACE_SLUG,
                    "email": test_email,
                    "password": TEST_PASSWORD,
                },
            )

            assert login_response.status_code == 200

            login_data = login_response.json()
            access_token = login_data["access_token"]

            authorization_headers = {
                "Authorization": (
                    f"Bearer {access_token}"
                )
            }

            unauthorized_upload_response = client.post(
                "/api/v1/documents/upload",
                files={
                    "file": (
                        test_filename,
                        pdf_data,
                        "application/pdf",
                    )
                },
            )

            assert (
                unauthorized_upload_response.status_code
                == 401
            )

            invalid_upload_response = client.post(
                "/api/v1/documents/upload",
                headers=authorization_headers,
                files={
                    "file": (
                        "malicious.exe",
                        b"unsafe-content",
                        "application/octet-stream",
                    )
                },
            )

            assert (
                invalid_upload_response.status_code
                == 415
            )

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

            assert upload_response.status_code == 201

            upload_data = upload_response.json()
            uploaded_document = upload_data["document"]

            assert upload_data["message"] == (
                "Document uploaded successfully."
            )

            assert (
                uploaded_document["original_filename"]
                == test_filename
            )

            assert (
                uploaded_document["content_type"]
                == "application/pdf"
            )

            assert (
                uploaded_document["file_extension"]
                == ".pdf"
            )

            assert (
                uploaded_document["document_type"]
                == "pdf"
            )

            assert (
                uploaded_document["status"]
                == "uploaded"
            )

            assert (
                uploaded_document["file_size_bytes"]
                == len(pdf_data)
            )

            assert (
                uploaded_document["checksum_sha256"]
                == expected_checksum
            )

            document_id = uploaded_document["id"]
            document_uuid = UUID(document_id)

            workspace_uuid = UUID(
                login_data["user"]["workspace_id"]
            )

            with SessionLocal() as database_session:
                database_document = (
                    database_session.scalar(
                        select(Document).where(
                            Document.id == document_uuid
                        )
                    )
                )

                assert database_document is not None

                storage_bucket = (
                    database_document.storage_bucket
                )

                storage_object_name = (
                    database_document.storage_object_name
                )

                assert (
                    database_document.workspace_id
                    == workspace_uuid
                )

                assert (
                    database_document.checksum_sha256
                    == expected_checksum
                )

            assert object_exists(
                bucket_name=storage_bucket,
                object_name=storage_object_name,
            ) is True

            list_response = client.get(
                "/api/v1/documents",
                headers=authorization_headers,
            )

            assert list_response.status_code == 200

            list_data = list_response.json()

            assert list_data["total"] >= 1
            assert list_data["limit"] == 20
            assert list_data["offset"] == 0

            listed_document_ids = {
                item["id"]
                for item in list_data["items"]
            }

            assert document_id in listed_document_ids

            filtered_list_response = client.get(
                "/api/v1/documents",
                headers=authorization_headers,
                params={
                    "status": "uploaded",
                    "document_type": "pdf",
                },
            )

            assert (
                filtered_list_response.status_code
                == 200
            )

            filtered_document_ids = {
                item["id"]
                for item
                in filtered_list_response.json()["items"]
            }

            assert document_id in filtered_document_ids

            detail_response = client.get(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert detail_response.status_code == 200

            detail_data = detail_response.json()

            assert detail_data["id"] == document_id
            assert (
                detail_data["original_filename"]
                == test_filename
            )

            download_response = client.get(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/download"
                ),
                headers=authorization_headers,
            )

            assert download_response.status_code == 200

            assert (
                download_response.content
                == pdf_data
            )

            assert (
                download_response.headers[
                    "content-type"
                ].startswith("application/pdf")
            )

            assert (
                download_response.headers[
                    "x-document-checksum-sha256"
                ]
                == expected_checksum
            )

            assert (
                test_filename
                in download_response.headers[
                    "content-disposition"
                ]
            )

            delete_response = client.delete(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert delete_response.status_code == 200

            delete_data = delete_response.json()

            assert delete_data["message"] == (
                "Document deleted successfully."
            )

            assert (
                delete_data["document_id"]
                == document_id
            )

            with SessionLocal() as database_session:
                deleted_document = (
                    database_session.scalar(
                        select(Document).where(
                            Document.id == document_uuid
                        )
                    )
                )

                assert deleted_document is None

            assert object_exists(
                bucket_name=storage_bucket,
                object_name=storage_object_name,
            ) is False

            deleted_detail_response = client.get(
                f"/api/v1/documents/{document_id}",
                headers=authorization_headers,
            )

            assert (
                deleted_detail_response.status_code
                == 404
            )

    finally:
        _cleanup_test_user(test_email)