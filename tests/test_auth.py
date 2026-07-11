from collections.abc import Generator
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.dependencies import get_database_session
from app.infrastructure.database.base import Base
from app.main import create_application

VALID_USER = {"email": "person@example.com", "password": "StrongPass123!"}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    application = create_application()
    application.dependency_overrides[get_database_session] = override_session
    with TestClient(application) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()


def register(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/register", json=VALID_USER)
    assert response.status_code == 201
    return response.json()


def test_successful_registration_returns_safe_user(client: TestClient) -> None:
    body = register(client)

    assert body["email"] == VALID_USER["email"]
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    register(client)
    response = client.post("/auth/register", json=VALID_USER)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


def test_successful_login_returns_access_token(client: TestClient) -> None:
    register(client)
    response = client.post("/auth/login", json=VALID_USER)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_invalid_credentials_are_rejected(client: TestClient) -> None:
    register(client)
    response = client.post("/auth/login", json={**VALID_USER, "password": "IncorrectPass123!"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_protected_route_returns_current_user(client: TestClient) -> None:
    user = register(client)
    token = client.post("/auth/login", json=VALID_USER).json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_protected_route_requires_authentication(client: TestClient) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["invalid.jwt.token", ""])
def test_invalid_tokens_are_rejected(client: TestClient, token: str) -> None:
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    user = register(client)
    expired_token = create_access_token(
        user_id=UUID(user["id"]), expires_delta=timedelta(seconds=-1)
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401


def test_registration_validates_email_and_password_strength(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": "bad", "password": "weak"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
