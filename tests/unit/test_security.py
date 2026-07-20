from __future__ import annotations

from datetime import timedelta

import pytest

from apps.api.app.core.security import (
    TokenDecodeError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plain_text() -> None:
    password = "StrongPassword123!"

    generated_hash = hash_password(password)

    assert generated_hash != password
    assert generated_hash.startswith("$argon2")


def test_correct_password_is_verified() -> None:
    password = "StrongPassword123!"
    generated_hash = hash_password(password)

    assert verify_password(
        password,
        generated_hash,
    ) is True


def test_incorrect_password_is_rejected() -> None:
    generated_hash = hash_password(
        "StrongPassword123!"
    )

    assert verify_password(
        "WrongPassword123!",
        generated_hash,
    ) is False


def test_access_token_contains_expected_claims() -> None:
    token = create_access_token(
        subject="user-123",
        additional_claims={
            "workspace_id": "workspace-123",
            "role": "administrator",
        },
    )

    payload = decode_token(
        token,
        expected_type="access",
    )

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["workspace_id"] == "workspace-123"
    assert payload["role"] == "administrator"
    assert payload["jti"]


def test_refresh_token_has_refresh_type() -> None:
    token = create_refresh_token(
        subject="user-123"
    )

    payload = decode_token(
        token,
        expected_type="refresh",
    )

    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    token = create_refresh_token(
        subject="user-123"
    )

    with pytest.raises(
        TokenDecodeError,
        match="Expected an access token",
    ):
        decode_token(
            token,
            expected_type="access",
        )


def test_expired_token_is_rejected() -> None:
    token = create_access_token(
        subject="user-123",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(TokenExpiredError):
        decode_token(
            token,
            expected_type="access",
        )


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(
        subject="user-123"
    )

    token_parts = token.split(".")

    assert len(token_parts) == 3

    header, payload, signature = token_parts

    tamper_position = len(signature) // 2
    original_character = signature[tamper_position]

    replacement_character = (
        "A"
        if original_character != "A"
        else "B"
    )

    tampered_signature = (
        signature[:tamper_position]
        + replacement_character
        + signature[tamper_position + 1:]
    )

    tampered_token = ".".join(
        [
            header,
            payload,
            tampered_signature,
        ]
    )

    assert tampered_token != token

    with pytest.raises(TokenDecodeError):
        decode_token(
            tampered_token,
            expected_type="access",
        )


def test_reserved_claims_cannot_be_overridden() -> None:
    with pytest.raises(
        ValueError,
        match="reserved JWT claims",
    ):
        create_access_token(
            subject="user-123",
            additional_claims={
                "sub": "different-user",
            },
        )