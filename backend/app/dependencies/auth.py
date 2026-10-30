"""NOVA — Supabase JWT Authentication Dependency.

Verifies Supabase Auth Bearer tokens. RS256/ES256 signatures are checked
against the configured project's JWKS. Legacy HS256 tokens are validated
online through that project's Auth user endpoint using its publishable key.
The verified Supabase user ID becomes the authenticated user identity.
Rejects missing, malformed, expired, or invalid tokens with HTTP 401.
Never logs tokens or private credentials.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
import structlog
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app.config import get_settings

logger = structlog.get_logger(__name__)

_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_SUPPORTED_ASYMMETRIC_ALGORITHMS = {"RS256", "ES256"}
_SUPPORTED_ALGORITHMS = _SUPPORTED_ASYMMETRIC_ALGORITHMS | {"HS256"}


class AuthenticatedUser(BaseModel):
    """Represents an authenticated Supabase user derived from a verified JWT."""

    id: str
    email: str | None = None
    role: str | None = None
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    """Return a cached PyJWKClient instance for the JWKS URL."""
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = jwt.PyJWKClient(
            jwks_url, cache_jwk_set=True, lifespan=3600, timeout=5
        )
    return _jwks_clients[jwks_url]


def verify_supabase_token(token: str) -> AuthenticatedUser:
    """
    Verify an asymmetric Supabase access token against the project's JWKS.

    Validates signature, expiration, audience, issuer, subject, and key ID.
    Returns AuthenticatedUser with the verified 'sub' claim as user ID.
    Raises HTTPException(401) on any failure without leaking credentials.
    """
    settings = get_settings()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception as exc:
        logger.warning("token_header_parse_failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token header",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    alg = unverified_header.get("alg")
    if alg not in _SUPPORTED_ASYMMETRIC_ALGORITHMS:
        logger.warning("unsupported_jwt_algorithm", alg=alg)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token algorithm",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    # Supabase asymmetric tokens must have an explicit issuer/project so we
    # never accept a token signed by an unrelated JWKS endpoint.
    if not settings.supabase_url or not settings.effective_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase project is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    kid = unverified_header.get("kid")
    if not isinstance(kid, str) or not kid.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token signing key ID is missing",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    # Determine signing key from this project's JWKS. PyJWKClient caches the
    # JWKS set and refreshes once when an unknown kid is encountered.
    try:
        jwks_url = settings.effective_jwks_url
        parsed_jwks = urlparse(jwks_url or "")
        parsed_project = urlparse(settings.supabase_url)
        local_host = parsed_jwks.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not jwks_url
            or parsed_jwks.hostname != parsed_project.hostname
            or parsed_jwks.port != parsed_project.port
            or (parsed_jwks.scheme != "https" and not local_host)
        ):
            raise ValueError("Supabase JWKS URL must use HTTPS and the project origin")
        client = _get_jwks_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
        if signing_key.key_id != kid:
            raise ValueError("JWKS returned a key with a mismatched kid")
        key = signing_key.key
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("signing_key_resolution_failed", alg=alg, error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to verify token signature key",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    # Decode and verify payload
    decode_options: dict[str, Any] = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": True,
        "require": ["exp", "sub", "aud", "iss"],
    }

    decode_kwargs: dict[str, Any] = {
        "algorithms": [alg],
        "options": decode_options,
    }

    decode_kwargs["audience"] = settings.supabase_jwt_audience

    # Verify issuer if configured
    decode_kwargs["issuer"] = settings.effective_issuer
    decode_options["verify_iss"] = True

    try:
        payload = jwt.decode(token, key, **decode_kwargs)
    except jwt.ExpiredSignatureError as exc:
        logger.info("token_expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="The access token expired"'},
        ) from exc
    except jwt.InvalidAudienceError as exc:
        logger.warning("token_invalid_audience")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc
    except jwt.InvalidIssuerError as exc:
        logger.warning("token_invalid_issuer")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc
    except (jwt.InvalidTokenError, jwt.PyJWTError) as exc:
        logger.warning("token_verification_failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature or claims",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc

    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        logger.warning("token_missing_subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identity",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    return AuthenticatedUser(
        id=user_id,
        email=payload.get("email"),
        role=payload.get("role"),
        app_metadata=payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {},
        user_metadata=payload.get("user_metadata") if isinstance(payload.get("user_metadata"), dict) else {},
    )


async def _verify_legacy_hs256_token(token: str) -> AuthenticatedUser:
    """Delegate legacy Supabase HMAC token validation to Supabase Auth."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase Auth is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    endpoint = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    try:
        parsed_endpoint = urlparse(endpoint)
        local_host = parsed_endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed_endpoint.scheme != "https" and not local_host:
            raise ValueError("Supabase Auth URL must use HTTPS")
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
            response = await client.get(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_publishable_key,
                },
            )
        if response.status_code != 200:
            raise ValueError("Supabase rejected the access token")
        user_data = response.json()
        user_id = user_data.get("id") if isinstance(user_data, dict) else None
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Supabase returned no user identity")
        return AuthenticatedUser(
            id=user_id,
            email=user_data.get("email"),
            app_metadata=user_data.get("app_metadata") if isinstance(user_data.get("app_metadata"), dict) else {},
            user_metadata=user_data.get("user_metadata") if isinstance(user_data.get("user_metadata"), dict) else {},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("supabase_user_validation_failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc


async def get_current_user(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency to authenticate requests using Bearer JWT.

    Rejects missing or invalid credentials with HTTP 401.
    Never trusts identity headers or query params.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed access token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc
    alg = header.get("alg")
    if alg not in _SUPPORTED_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported token algorithm",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    if alg == "HS256":
        return await _verify_legacy_hs256_token(token)
    return verify_supabase_token(token)


async def get_current_user_id(request: Request) -> str:
    """Convenience dependency returning the verified user's ID directly."""
    user = await get_current_user(request)
    return user.id
