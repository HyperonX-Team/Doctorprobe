"""Shared pytest fixtures.

The test suite runs against an in-memory async SQLite database so it is
fast, isolated, and requires no external services. Tables are created
fresh per session via ``Base.metadata.create_all``.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite engine with schema created."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(db_engine):
    """HTTP client with the app wired to the test database."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def created_user(client):
    """Helper: create a user and return the response body."""
    payload = {
        "age": 34,
        "sex": "female",
        "height_cm": 165.0,
        "weight_kg": 62.0,
        "activity_level": "moderate",
        "share_data": True,
        "device_id": "doctordrobe_demo_001",
    }
    response = await client.post("/api/users", json=payload)
    assert response.status_code == 201, response.text
    return response.json()
