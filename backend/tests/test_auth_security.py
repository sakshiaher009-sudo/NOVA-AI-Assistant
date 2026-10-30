"""Authentication and tenant-isolation regression tests."""

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.database.database import get_db_session
from app.database.repositories import (
    ChunkRepo,
    ConversationRepo,
    DocumentRepo,
    MessageRepo,
    ReminderRepo,
)
from app.dependencies import auth
from app.dependencies.auth import get_current_user, get_current_user_id
from app.main import app

ISSUER = "https://nova-test.supabase.co/auth/v1"
AUDIENCE = "authenticated"


def request_with_auth(value: str | None = None) -> Request:
    headers = [] if value is None else [(b"authorization", value.encode())]
    return Request({"type": "http", "headers": headers, "method": "GET", "path": "/"})


def make_rsa_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def make_rsa_token(private_key, *, kid="key-a", sub="user-a", exp=None, iss=ISSUER, aud=AUDIENCE):
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "exp": exp or now + timedelta(minutes=5),
        "iat": now,
    }
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def configure_jwks(monkeypatch, public_key):
    settings = SimpleNamespace(
        supabase_url="https://nova-test.supabase.co",
        effective_issuer=ISSUER,
        effective_jwks_url="https://nova-test.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_jwt_audience=AUDIENCE,
        supabase_publishable_key="test-publishable-key",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            kid = jwt.get_unverified_header(token).get("kid")
            if kid != "key-a":
                raise jwt.PyJWKClientError("No matching signing key")
            return SimpleNamespace(key_id=kid, key=public_key)

    monkeypatch.setattr(auth, "_get_jwks_client", lambda _url: FakeJwks())
    return settings


@pytest.mark.asyncio
async def test_missing_and_malformed_bearer_tokens_return_401(monkeypatch):
    configure_jwks(monkeypatch, make_rsa_pair()[1])
    with pytest.raises(HTTPException) as missing:
        await get_current_user(request_with_auth())
    assert missing.value.status_code == 401

    for header in ("Basic abc", "Bearer", "Bearer not-a-jwt", "Bearer   "):
        with pytest.raises(HTTPException) as invalid:
            await get_current_user(request_with_auth(header))
        assert invalid.value.status_code == 401

    unsigned = jwt.encode({"sub": "user-a"}, key="", algorithm="none")
    with pytest.raises(HTTPException) as unsupported:
        await get_current_user(request_with_auth(f"Bearer {unsigned}"))
    assert unsupported.value.status_code == 401


def test_jwks_client_is_cached_with_bounded_fetch_timeout(monkeypatch):
    constructed = []

    class FakeJwksClient:
        def __init__(self, url, **kwargs):
            constructed.append((url, kwargs))

    monkeypatch.setattr(auth.jwt, "PyJWKClient", FakeJwksClient)
    auth._jwks_clients.clear()
    url = "https://nova-test.supabase.co/auth/v1/.well-known/jwks.json"
    first = auth._get_jwks_client(url)
    second = auth._get_jwks_client(url)
    assert first is second
    assert len(constructed) == 1
    assert constructed[0][1] == {
        "cache_jwk_set": True,
        "lifespan": 3600,
        "timeout": 5,
    }
    auth._jwks_clients.pop(url, None)


@pytest.mark.asyncio
async def test_valid_supabase_jwks_token_uses_verified_subject(monkeypatch):
    private_key, public_key = make_rsa_pair()
    configure_jwks(monkeypatch, public_key)
    user = await get_current_user(request_with_auth(f"Bearer {make_rsa_token(private_key)}"))
    assert user.id == "user-a"


@pytest.mark.asyncio
async def test_invalid_signature_and_unknown_kid_return_401(monkeypatch):
    trusted_private, trusted_public = make_rsa_pair()
    attacker_private, _ = make_rsa_pair()
    configure_jwks(monkeypatch, trusted_public)
    for token in (
        make_rsa_token(attacker_private),
        make_rsa_token(trusted_private, kid="unknown-kid"),
    ):
        with pytest.raises(HTTPException) as invalid:
            await get_current_user(request_with_auth(f"Bearer {token}"))
        assert invalid.value.status_code == 401


@pytest.mark.asyncio
async def test_jwks_override_must_match_supabase_project_origin(monkeypatch):
    private_key, public_key = make_rsa_pair()
    settings = configure_jwks(monkeypatch, public_key)
    settings.effective_jwks_url = "https://attacker.invalid/jwks.json"
    token = make_rsa_token(private_key)
    with pytest.raises(HTTPException) as invalid:
        await get_current_user(request_with_auth(f"Bearer {token}"))
    assert invalid.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claims",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iss": "https://attacker.invalid/auth/v1"},
        {"aud": "other-audience"},
    ],
)
async def test_expiration_issuer_and_audience_are_required(monkeypatch, claims):
    private_key, public_key = make_rsa_pair()
    configure_jwks(monkeypatch, public_key)
    token = make_rsa_token(private_key, **claims)
    with pytest.raises(HTTPException) as invalid:
        await get_current_user(request_with_auth(f"Bearer {token}"))
    assert invalid.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_hs256_validation_calls_supabase_user_endpoint(monkeypatch):
    settings = configure_jwks(monkeypatch, make_rsa_pair()[1])
    settings.supabase_publishable_key = "publishable-test-value"
    calls = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "supabase-user-7", "email": "member@example.test"}

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, headers):
            calls.append((url, headers))
            return FakeResponse()

    monkeypatch.setattr(auth.httpx, "AsyncClient", FakeClient)
    legacy = jwt.encode(
        {"sub": "untrusted-until-remote-validation"},
        "opaque-test-signature-key-at-least-32-bytes",
        algorithm="HS256",
    )
    user = await get_current_user(request_with_auth(f"Bearer {legacy}"))
    assert user.id == "supabase-user-7"
    assert calls[0][0] == "https://nova-test.supabase.co/auth/v1/user"
    assert calls[0][1]["Authorization"] == f"Bearer {legacy}"
    assert calls[0][1]["apikey"] == "publishable-test-value"


@pytest.mark.asyncio
async def test_hs256_rejected_when_supabase_auth_rejects_token(monkeypatch):
    settings = configure_jwks(monkeypatch, make_rsa_pair()[1])
    settings.jwt_secret = "local-only-secret-must-not-be-used"

    class RejectingClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=401)

    monkeypatch.setattr(auth.httpx, "AsyncClient", RejectingClient)
    token = jwt.encode({"sub": "user-a"}, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(HTTPException) as invalid:
        await get_current_user(request_with_auth(f"Bearer {token}"))
    assert invalid.value.status_code == 401


@pytest_asyncio.fixture
async def api_client():
    async def identify_user(request: Request):
        return request.headers.get("x-test-user", "user-a")

    app.dependency_overrides[get_current_user_id] = identify_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.mark.asyncio
async def test_health_is_public_and_private_routes_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/health")).status_code == 200
        api_paths = app.openapi()["paths"]
        assert "/api/health" in api_paths
        assert "/api/status" in api_paths
        for path, operations in api_paths.items():
            if not path.startswith("/api/") or path in {"/api/health", "/api/status"}:
                continue
            request_path = re.sub(r"\{[^/]+\}", "test-resource-id", path)
            for method in ("get", "post", "put", "patch", "delete"):
                if method in operations:
                    response = await client.request(method.upper(), request_path)
                    assert response.status_code == 401, f"{method.upper()} {path} was public"


@pytest.mark.asyncio
async def test_two_users_cannot_read_update_or_delete_each_others_notes(api_client):
    created = await api_client.post(
        "/api/notes", headers={"x-test-user": "user-a"},
        json={"title": "A private note", "content": "owner A"},
    )
    assert created.status_code == 200
    note_id = created.json()["id"]
    other_created = await api_client.post(
        "/api/notes", headers={"x-test-user": "user-b"},
        json={"title": "B private note", "content": "owner B"},
    )
    assert other_created.status_code == 200
    other_note_id = other_created.json()["id"]

    other_list = await api_client.get("/api/notes", headers={"x-test-user": "user-b"})
    assert {row["id"] for row in other_list.json()} == {other_note_id}
    assert (await api_client.put(
        f"/api/notes/{note_id}", headers={"x-test-user": "user-b"},
        json={"title": "stolen"},
    )).status_code == 404
    assert (await api_client.delete(
        f"/api/notes/{note_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404
    assert (await api_client.get(
        "/api/notes", headers={"x-test-user": "user-a"},
    )).json()[0]["title"] == "A private note"


@pytest.mark.asyncio
async def test_parent_and_child_conversation_ownership_isolated(api_client):
    async with get_db_session() as session:
        conv = await ConversationRepo.create(session, title="A conversation", user_id="user-a")
        await MessageRepo.create(session, conv.id, "user", "secret", user_id="user-a")
        conv_id = conv.id

    assert (await api_client.get(
        f"/api/conversations/{conv_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404
    assert (await api_client.delete(
        f"/api/conversations/{conv_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404
    async with get_db_session() as session:
        assert await MessageRepo.get_by_conversation(session, conv_id, user_id="user-b") == []
        with pytest.raises(ValueError):
            await MessageRepo.create(session, conv_id, "user", "forbidden", user_id="user-b")


@pytest.mark.asyncio
async def test_document_and_chunk_parent_ownership_isolated(api_client):
    async with get_db_session() as session:
        doc = await DocumentRepo.create(
            session, "a.txt", "a.txt", "txt", 1, user_id="user-a"
        )
        doc_id = doc.id
        await ChunkRepo.create_many(session, doc_id, ["private chunk"], user_id="user-a")
        with pytest.raises(ValueError):
            await ChunkRepo.create_many(session, doc_id, ["cross-user"], user_id="user-b")
        assert await ChunkRepo.get_by_document(session, doc_id, user_id="user-b") == []
    assert (await api_client.get(
        f"/api/documents/{doc_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404
    assert (await api_client.delete(
        f"/api/documents/{doc_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404


@pytest.mark.asyncio
async def test_reminder_owner_filter_isolation(api_client):
    async with get_db_session() as session:
        reminder = await ReminderRepo.create(session, "A reminder", user_id="user-a")
        reminder_id = reminder.id
    assert (await api_client.get(
        "/api/reminders", headers={"x-test-user": "user-b"},
    )).json() == []
    assert (await api_client.put(
        f"/api/reminders/{reminder_id}", headers={"x-test-user": "user-b"},
        json={"title": "stolen"},
    )).status_code == 404
    assert (await api_client.delete(
        f"/api/reminders/{reminder_id}", headers={"x-test-user": "user-b"},
    )).status_code == 404
