from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
import csv
from io import BytesIO, StringIO
from zipfile import ZipFile

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.app.db.models.document import (
    Document,
)
from apps.api.app.db.models.user import (
    User,
)
from apps.api.app.db.models.workspace import (
    Carrier,
    Customer,
    Plan,
    Policy,
    Workspace,
)
from apps.api.app.db.session import (
    SessionLocal,
)
from apps.api.app.main import app
from apps.api.app.services.storage import (
    StorageError,
    delete_object,
)


WORKSPACE_SLUG = (
    "insightops-insurance-demo"
)

TEST_PASSWORD = (
    "StrongPassword123!"
)

TEST_POLICY_NUMBER = (
    "POL-2026-0020"
)

PROCESSING_TIMEOUT_SECONDS = 180

PROCESSING_POLL_INTERVAL_SECONDS = 1


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyTestFixture:
    policy_number: str
    customer_name: str
    carrier_name: str
    plan_name: str

    database_effective_date: date
    document_effective_date: date
    signature_date: date

    premium: Decimal
    policy_status: str


def get_demo_workspace_id() -> UUID:
    """
    Return the seeded demonstration workspace ID.
    """

    with SessionLocal() as database_session:
        workspace_id = (
            database_session.scalar(
                select(
                    Workspace.id
                ).where(
                    Workspace.slug
                    == WORKSPACE_SLUG
                )
            )
        )

    assert workspace_id is not None, (
        "The demonstration workspace is missing. "
        "Run the demo seed script first."
    )

    return workspace_id


def load_policy_fixture(
    *,
    workspace_id: UUID,
) -> PolicyTestFixture:
    """
    Load a deterministic active policy from the seeded dataset.

    The PDF intentionally uses a different effective date so the
    reconciliation workflow creates a human-review task.
    """

    with SessionLocal() as database_session:
        policy = database_session.scalar(
            select(Policy).where(
                Policy.workspace_id
                == workspace_id,
                Policy.policy_number
                == TEST_POLICY_NUMBER,
                Policy.source_system
                == "synthetic_policy_admin",
            )
        )

        assert policy is not None, (
            f"Seeded policy "
            f"{TEST_POLICY_NUMBER} "
            "was not found."
        )

        customer = database_session.get(
            Customer,
            policy.customer_id,
        )

        carrier = database_session.get(
            Carrier,
            policy.carrier_id,
        )

        plan = database_session.get(
            Plan,
            policy.plan_id,
        )

        assert customer is not None
        assert carrier is not None
        assert plan is not None

        customer_name = " ".join(
            value.strip()
            for value in (
                customer.first_name,
                customer.last_name,
            )
            if value and value.strip()
        )

        database_effective_date = (
            policy.effective_date
        )

        assert (
            database_effective_date
            is not None
        )

        document_effective_date = (
            database_effective_date
            + timedelta(days=1)
        )

        signature_date = (
            database_effective_date
            - timedelta(days=10)
        )

        premium = Decimal(
            str(policy.premium)
        ).quantize(
            Decimal("0.01")
        )

        return PolicyTestFixture(
            policy_number=(
                policy.policy_number
            ),
            customer_name=customer_name,
            carrier_name=carrier.name,
            plan_name=plan.name,
            database_effective_date=(
                database_effective_date
            ),
            document_effective_date=(
                document_effective_date
            ),
            signature_date=signature_date,
            premium=premium,
            policy_status=policy.status,
        )


def create_policy_test_pdf(
    *,
    fixture: PolicyTestFixture,
    unique_identifier: str,
) -> bytes:
    """
    Create a selectable policy PDF containing one intentional mismatch.
    """

    pdf_document = pymupdf.open()

    try:
        page = pdf_document.new_page()

        lines = [
            (
                "InsightOps Policy "
                "Reconciliation Test"
            ),
            (
                f"Test Reference: "
                f"{unique_identifier}"
            ),
            (
                f"Policy Number: "
                f"{fixture.policy_number}"
            ),
            (
                f"Policyholder Name: "
                f"{fixture.customer_name}"
            ),
            (
                f"Carrier: "
                f"{fixture.carrier_name}"
            ),
            (
                f"Plan Name: "
                f"{fixture.plan_name}"
            ),
            (
                "Effective Date: "
                f"{fixture.document_effective_date.strftime(
                    '%m/%d/%Y'
                )}"
            ),
            (
                "Signature Date: "
                f"{fixture.signature_date.strftime(
                    '%m/%d/%Y'
                )}"
            ),
            (
                f"Premium Amount: "
                f"${fixture.premium:,.2f}"
            ),
            (
                f"Policy Status: "
                f"{fixture.policy_status.title()}"
            ),
        ]

        vertical_position = 72

        for line_index, line in enumerate(
            lines
        ):
            page.insert_text(
                (
                    72,
                    vertical_position,
                ),
                line,
                fontsize=(
                    14
                    if line_index == 0
                    else 11
                ),
            )

            vertical_position += 28

        return pdf_document.tobytes()

    finally:
        pdf_document.close()


def cleanup_test_user(
    *,
    workspace_id: UUID,
    email: str,
) -> None:
    """
    Remove the test user, documents, storage objects, processing runs,
    reconciliation runs, findings, and review tasks.

    Database cascades remove document-owned reconciliation data.
    """

    with SessionLocal() as database_session:
        user = database_session.scalar(
            select(User).where(
                User.workspace_id
                == workspace_id,
                User.email == email,
            )
        )

        if user is None:
            return

        documents = list(
            database_session.scalars(
                select(Document).where(
                    Document.workspace_id
                    == workspace_id,
                    Document.uploaded_by_user_id
                    == user.id,
                )
            ).all()
        )

        for document in documents:
            try:
                delete_object(
                    bucket_name=(
                        document.storage_bucket
                    ),
                    object_name=(
                        document.storage_object_name
                    ),
                )
            except StorageError:
                pass

            database_session.delete(
                document
            )

        database_session.flush()

        database_session.delete(
            user
        )

        database_session.commit()


def wait_for_processing_completion(
    *,
    client: TestClient,
    headers: dict[str, str],
    document_id: str,
) -> dict[str, object]:
    """
    Poll the document-processing endpoint until completion.
    """

    deadline = (
        time.monotonic()
        + PROCESSING_TIMEOUT_SECONDS
    )

    latest_run: dict[
        str,
        object,
    ] | None = None

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

        processing_runs = (
            response_data["items"]
        )

        if processing_runs:
            latest_run = (
                processing_runs[0]
            )

            run_status = latest_run[
                "status"
            ]

            if run_status == "completed":
                return latest_run

            if run_status == "failed":
                raise AssertionError(
                    "Document processing failed: "
                    f"{latest_run.get(
                        'error_message'
                    )}"
                )

        time.sleep(
            PROCESSING_POLL_INTERVAL_SECONDS
        )

    raise AssertionError(
        "Document processing did not finish "
        f"within "
        f"{PROCESSING_TIMEOUT_SECONDS} "
        "seconds. "
        f"Latest run: {latest_run}"
    )


def test_complete_reconciliation_api_flow() -> None:
    workspace_id = (
        get_demo_workspace_id()
    )

    policy_fixture = (
        load_policy_fixture(
            workspace_id=workspace_id,
        )
    )

    unique_identifier = (
        uuid4().hex[:12]
    )

    test_email = (
        "reconciliation-test-"
        f"{unique_identifier}"
        "@example.com"
    )

    test_filename = (
        "reconciliation-test-"
        f"{unique_identifier}.pdf"
    )

    pdf_data = (
        create_policy_test_pdf(
            fixture=policy_fixture,
            unique_identifier=(
                unique_identifier
            ),
        )
    )

    cleanup_test_user(
        workspace_id=workspace_id,
        email=test_email,
    )

    try:
        with TestClient(app) as client:
            unauthorized_response = (
                client.get(
                    "/api/v1/reconciliation/runs"
                )
            )

            assert (
                unauthorized_response
                .status_code
                == 401
            )

            registration_response = (
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "workspace_slug":
                            WORKSPACE_SLUG,
                        "email":
                            test_email,
                        "full_name": (
                            "Reconciliation "
                            "Integration Test User"
                        ),
                        "password":
                            TEST_PASSWORD,
                    },
                )
            )

            assert (
                registration_response
                .status_code
                == 201
            ), registration_response.text

            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "workspace_slug":
                        WORKSPACE_SLUG,
                    "email":
                        test_email,
                    "password":
                        TEST_PASSWORD,
                },
            )

            assert (
                login_response.status_code
                == 200
            ), login_response.text

            login_data = (
                login_response.json()
            )

            authorization_headers = {
                "Authorization": (
                    "Bearer "
                    f"{login_data[
                        'access_token'
                    ]}"
                )
            }

            current_user_response = (
                client.get(
                    "/api/v1/auth/me",
                    headers=(
                        authorization_headers
                    ),
                )
            )

            assert (
                current_user_response
                .status_code
                == 200
            ), current_user_response.text

            current_user_data = (
                current_user_response.json()
            )

            current_user_id = (
                current_user_data[
                    "user"
                ]["id"]
            )

            upload_response = client.post(
                "/api/v1/documents/upload",
                headers=(
                    authorization_headers
                ),
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
                upload_response.json()[
                    "document"
                ]
            )

            document_id = (
                uploaded_document["id"]
            )

            process_response = client.post(
                (
                    f"/api/v1/documents/"
                    f"{document_id}/process"
                ),
                headers=(
                    authorization_headers
                ),
                params={
                    "ocr_language": "eng",
                },
            )

            assert (
                process_response.status_code
                == 202
            ), process_response.text

            completed_processing_run = (
                wait_for_processing_completion(
                    client=client,
                    headers=(
                        authorization_headers
                    ),
                    document_id=document_id,
                )
            )

            assert (
                completed_processing_run[
                    "status"
                ]
                == "completed"
            )

            reconciliation_response = (
                client.post(
                    (
                        "/api/v1/reconciliation/"
                        f"documents/{document_id}/run"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    json={
                        "minimum_confidence":
                            0.75,
                        "premium_tolerance":
                            "0.01",
                        "exclude_cancelled":
                            True,
                    },
                )
            )

            assert (
                reconciliation_response
                .status_code
                == 201
            ), reconciliation_response.text

            reconciliation_data = (
                reconciliation_response.json()
            )

            assert (
                reconciliation_data["message"]
                == (
                    "Document reconciliation "
                    "completed."
                )
            )

            reconciliation_run = (
                reconciliation_data["run"]
            )

            run_id = (
                reconciliation_run["id"]
            )

            assert (
                reconciliation_run[
                    "document_id"
                ]
                == document_id
            )

            assert (
                reconciliation_run[
                    "processing_run_id"
                ]
                == completed_processing_run[
                    "id"
                ]
            )

            assert (
                reconciliation_run["status"]
                == "needs_review"
            )

            assert (
                reconciliation_run[
                    "failed_checks"
                ]
                >= 1
            )

            assert (
                reconciliation_run[
                    "total_checks"
                ]
                == len(
                    reconciliation_data[
                        "findings"
                    ]
                )
            )

            extraction = (
                reconciliation_data[
                    "extraction"
                ]
            )

            assert (
                extraction["fields"][
                    "policy_number"
                ]["value"]
                == policy_fixture.policy_number
            )

            assert (
                extraction["fields"][
                    "effective_date"
                ]["value"]
                == (
                    policy_fixture
                    .document_effective_date
                    .isoformat()
                )
            )

            findings_by_rule = {
                finding["rule_code"]:
                    finding
                for finding in (
                    reconciliation_data[
                        "findings"
                    ]
                )
            }

            effective_date_finding = (
                findings_by_rule["REC006"]
            )

            assert (
                effective_date_finding[
                    "status"
                ]
                == "failed"
            )

            assert (
                effective_date_finding[
                    "severity"
                ]
                == "high"
            )

            assert (
                effective_date_finding[
                    "finding_type"
                ]
                == "effective_date"
            )

            assert (
                effective_date_finding[
                    "expected_value"
                ]
                == (
                    policy_fixture
                    .database_effective_date
                    .isoformat()
                )
            )

            assert (
                effective_date_finding[
                    "actual_value"
                ]
                == (
                    policy_fixture
                    .document_effective_date
                    .isoformat()
                )
            )

            assert (
                effective_date_finding[
                    "source_page_number"
                ]
                == 1
            )

            assert (
                "Effective Date"
                in (
                    effective_date_finding[
                        "source_text"
                    ]
                    or ""
                )
            )

            review_tasks = (
                reconciliation_data[
                    "review_tasks"
                ]
            )

            assert review_tasks

            effective_date_task = next(
                task
                for task in review_tasks
                if (
                    task[
                        "extra_metadata"
                    ]["rule_code"]
                    == "REC006"
                )
            )

            review_task_id = (
                effective_date_task["id"]
            )

            assert (
                effective_date_task[
                    "status"
                ]
                == "open"
            )

            assert (
                effective_date_task[
                    "priority"
                ]
                == "high"
            )

            runs_list_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/runs"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    params={
                        "document_id":
                            document_id,
                    },
                )
            )

            assert (
                runs_list_response
                .status_code
                == 200
            ), runs_list_response.text

            runs_list_data = (
                runs_list_response.json()
            )

            assert (
                runs_list_data["total"]
                >= 1
            )

            assert any(
                item["id"] == run_id
                for item in (
                    runs_list_data[
                        "items"
                    ]
                )
            )

            run_detail_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/runs/"
                        f"{run_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                )
            )

            assert (
                run_detail_response
                .status_code
                == 200
            )

            assert (
                run_detail_response.json()[
                    "id"
                ]
                == run_id
            )

            unauthorized_csv_response = (
                client.get(
                    (
                        "/api/v1/reconciliation/"
                        f"runs/{run_id}/reports/csv"
                    )
                )
            )

            assert (
                unauthorized_csv_response
                .status_code
                == 401
            )

            csv_report_response = client.get(
                (
                    "/api/v1/reconciliation/"
                    f"runs/{run_id}/reports/csv"
                ),
                headers=authorization_headers,
            )

            assert (
                csv_report_response.status_code
                == 200
            ), csv_report_response.text

            assert (
                csv_report_response.headers[
                    "content-type"
                ].startswith(
                    "text/csv"
                )
            )

            csv_disposition = (
                csv_report_response.headers[
                    "content-disposition"
                ]
            )

            assert (
                "attachment"
                in csv_disposition
            )

            assert (
                ".csv"
                in csv_disposition
            )

            csv_text = (
                csv_report_response.content
                .decode(
                    "utf-8-sig"
                )
            )

            csv_rows = list(
                csv.DictReader(
                    StringIO(
                        csv_text
                    )
                )
            )

            assert csv_rows

            assert any(
                row["rule_code"]
                == "REC006"
                for row in csv_rows
            )

            effective_date_csv_row = next(
                row
                for row in csv_rows
                if row["rule_code"]
                == "REC006"
            )

            assert (
                effective_date_csv_row[
                    "finding_status"
                ]
                == "failed"
            )

            assert (
                effective_date_csv_row[
                    "expected_value"
                ]
                == (
                    policy_fixture
                    .database_effective_date
                    .isoformat()
                )
            )

            assert (
                effective_date_csv_row[
                    "actual_value"
                ]
                == (
                    policy_fixture
                    .document_effective_date
                    .isoformat()
                )
            )

            xlsx_report_response = client.get(
                (
                    "/api/v1/reconciliation/"
                    f"runs/{run_id}/reports/xlsx"
                ),
                headers=authorization_headers,
            )

            assert (
                xlsx_report_response.status_code
                == 200
            ), xlsx_report_response.text

            expected_xlsx_media_type = (
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            )

            assert (
                xlsx_report_response.headers[
                    "content-type"
                ].startswith(
                    expected_xlsx_media_type
                )
            )

            xlsx_disposition = (
                xlsx_report_response.headers[
                    "content-disposition"
                ]
            )

            assert (
                "attachment"
                in xlsx_disposition
            )

            assert (
                ".xlsx"
                in xlsx_disposition
            )

            assert (
                xlsx_report_response.content
                .startswith(
                    b"PK"
                )
            )

            with ZipFile(
                BytesIO(
                    xlsx_report_response.content
                )
            ) as workbook_archive:
                workbook_xml = (
                    workbook_archive.read(
                        "xl/workbook.xml"
                    ).decode(
                        "utf-8"
                    )
                )

            assert (
                'name="Summary"'
                in workbook_xml
            )

            assert (
                'name="Findings"'
                in workbook_xml
            )

            assert (
                'name="Review Tasks"'
                in workbook_xml
            )

            missing_report_response = (
                client.get(
                    (
                        "/api/v1/reconciliation/"
                        f"runs/{uuid4()}/reports/csv"
                    ),
                    headers=authorization_headers,
                )
            )

            assert (
                missing_report_response
                .status_code
                == 404
            )

            failed_findings_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/runs/"
                        f"{run_id}/findings"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    params={
                        "status": "failed",
                        "severity": "high",
                    },
                )
            )

            assert (
                failed_findings_response
                .status_code
                == 200
            ), failed_findings_response.text

            failed_findings_data = (
                failed_findings_response
                .json()
            )

            assert any(
                finding["rule_code"]
                == "REC006"
                for finding in (
                    failed_findings_data[
                        "items"
                    ]
                )
            )

            open_tasks_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    params={
                        "run_id": run_id,
                        "status": "open",
                    },
                )
            )

            assert (
                open_tasks_response
                .status_code
                == 200
            ), open_tasks_response.text

            assert any(
                task["id"]
                == review_task_id
                for task in (
                    open_tasks_response
                    .json()["items"]
                )
            )

            task_detail_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks/"
                        f"{review_task_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                )
            )

            assert (
                task_detail_response
                .status_code
                == 200
            )

            assign_task_response = (
                client.patch(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks/"
                        f"{review_task_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    json={
                        "assigned_to_user_id":
                            current_user_id,
                        "status":
                            "in_progress",
                    },
                )
            )

            assert (
                assign_task_response
                .status_code
                == 200
            ), assign_task_response.text

            assigned_task = (
                assign_task_response.json()[
                    "task"
                ]
            )

            assert (
                assigned_task[
                    "assigned_to_user_id"
                ]
                == current_user_id
            )

            assert (
                assigned_task["status"]
                == "in_progress"
            )

            resolve_task_response = (
                client.patch(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks/"
                        f"{review_task_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    json={
                        "status":
                            "corrected",
                        "resolution_notes": (
                            "Verified the source "
                            "document and corrected "
                            "the effective date."
                        ),
                        "corrected_value": (
                            policy_fixture
                            .database_effective_date
                            .isoformat()
                        ),
                    },
                )
            )

            assert (
                resolve_task_response
                .status_code
                == 200
            ), resolve_task_response.text

            resolved_task = (
                resolve_task_response.json()[
                    "task"
                ]
            )

            assert (
                resolved_task["status"]
                == "corrected"
            )

            assert (
                resolved_task[
                    "corrected_value"
                ]
                == (
                    policy_fixture
                    .database_effective_date
                    .isoformat()
                )
            )

            assert (
                resolved_task[
                    "resolved_by_user_id"
                ]
                == current_user_id
            )

            assert (
                resolved_task[
                    "resolved_at"
                ]
                is not None
            )

            corrected_tasks_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    params={
                        "run_id": run_id,
                        "status": "corrected",
                    },
                )
            )

            assert (
                corrected_tasks_response
                .status_code
                == 200
            )

            assert any(
                task["id"]
                == review_task_id
                for task in (
                    corrected_tasks_response
                    .json()["items"]
                )
            )

            reopen_response = (
                client.patch(
                    (
                        "/api/v1/"
                        "reconciliation/"
                        "review-tasks/"
                        f"{review_task_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                    json={
                        "status": "open",
                    },
                )
            )

            assert (
                reopen_response.status_code
                == 409
            )

            delete_document_response = (
                client.delete(
                    (
                        f"/api/v1/documents/"
                        f"{document_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                )
            )

            assert (
                delete_document_response
                .status_code
                == 200
            ), delete_document_response.text

            deleted_run_response = (
                client.get(
                    (
                        "/api/v1/"
                        "reconciliation/runs/"
                        f"{run_id}"
                    ),
                    headers=(
                        authorization_headers
                    ),
                )
            )

            assert (
                deleted_run_response
                .status_code
                == 404
            )

    finally:
        cleanup_test_user(
            workspace_id=workspace_id,
            email=test_email,
        )