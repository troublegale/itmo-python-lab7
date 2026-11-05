import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app


@pytest_asyncio.fixture
async def client():
    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://tasks:tasks@localhost:5433/tasks_test",
    )
    if make_url(url).database != "tasks_test":
        raise RuntimeError("Tests must use the dedicated tasks_test database")
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE tasks, users RESTART IDENTITY CASCADE"))

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest_asyncio.fixture
async def owner(client):
    return (
        await client.post(
            "/users", json={"name": "Alice", "email": "alice@example.com"}
        )
    ).json()


@pytest_asyncio.fixture
async def task(client, owner):
    return (
        await client.post(
            "/tasks",
            json={"title": "Read", "description": "Book", "owner_id": owner["id"]},
        )
    ).json()
