from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from apps.api.app.core.config import settings


TokenType = Literal["access", "refresh"]

password_hasher = PasswordHash.recommended()


class TokenDecodeError(ValueError):
    """Raised when a JWT token cannot be securely decoded."""


class TokenExpiredError(TokenDecodeError):
    """Raised when a JWT token has expired."""


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using pwdlib's recommended algorithm.

    Argon2 is currently used by PasswordHash.recommended().
    """

    if not plain_password:
        raise ValueError("Password cannot be empty.")

    return password_hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Return True when a plain password matches the stored hash."""

    if not plain_password or not password_hash:
        return False

    try:
        return password_hasher.verify(
            plain_password,
            password_hash,
        )
    except (TypeError, ValueError):
        return False


def _create_token(
    subject: str | UUID,
    token_type: TokenType,
    expires_delta: timedelta,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create and sign a JWT token."""

    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }

    if additional_claims:
        reserved_claims = {
            "sub",
            "type",
            "iat",
            "exp",
            "jti",
        }

        invalid_claims = (
            reserved_claims
            & additional_claims.keys()
        )

        if invalid_claims:
            raise ValueError(
                "Additional claims cannot override reserved "
                f"JWT claims: {sorted(invalid_claims)}"
            )

        payload.update(additional_claims)

    return jwt.encode(
        payload=payload,
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    subject: str | UUID,
    additional_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access token."""

    token_lifetime = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )

    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=token_lifetime,
        additional_claims=additional_claims,
    )


def create_refresh_token(
    subject: str | UUID,
    additional_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed refresh token."""

    token_lifetime = expires_delta or timedelta(
        days=settings.refresh_token_expire_days
    )

    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=token_lifetime,
        additional_claims=additional_claims,
    )


def _token_article(token_type: str) -> str:
    """Return the correct English article for a token type."""

    if token_type == "access":
        return "an"

    return "a"


def decode_token(
    token: str,
    expected_type: TokenType | None = None,
) -> dict[str, Any]:
    """
    Validate and decode a JWT token.

    The token signature, required claims, and expiration time are verified.
    """

    if not token:
        raise TokenDecodeError("Token cannot be empty.")

    try:
        payload = jwt.decode(
            jwt=token,
            key=settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": [
                    "sub",
                    "type",
                    "iat",
                    "exp",
                    "jti",
                ]
            },
        )
    except ExpiredSignatureError as error:
        raise TokenExpiredError(
            "Authentication token has expired."
        ) from error
    except InvalidTokenError as error:
        raise TokenDecodeError(
            "Authentication token is invalid."
        ) from error

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not isinstance(subject, str) or not subject:
        raise TokenDecodeError(
            "Authentication token is missing its subject."
        )

    if token_type not in {"access", "refresh"}:
        raise TokenDecodeError(
            "Authentication token has an invalid token type."
        )

    if expected_type and token_type != expected_type:
        expected_article = _token_article(expected_type)
        received_article = _token_article(token_type)

        raise TokenDecodeError(
            f"Expected {expected_article} {expected_type} token, "
            f"received {received_article} {token_type} token."
        )

    return payload