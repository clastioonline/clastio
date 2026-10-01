"""Test setup: real Postgres (pgvector) test database, offline AI provider, jobs executed inline."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/teacher_assistant_test")
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_OFFLINE_MODE"] = "true"
os.environ["RUN_JOBS_INLINE"] = "true"
os.environ["OPENVERSE_ENABLED"] = "false"
os.environ["STORAGE_LOCAL_DIR"] = tempfile.mkdtemp(prefix="ata-test-storage-")
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_secret"
os.environ["DODO_PAYMENTS_WEBHOOK_KEY"] = "whsec_dGVzdC1kb2RvLXdlYmhvb2stc2VjcmV0LTEyMzQ="
os.environ["DODO_PAYMENTS_API_KEY"] = ""
os.environ["WHATSAPP_APP_SECRET"] = "wa_test_secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "verify-me"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


@pytest.fixture(scope="session", autouse=True)
def database():
    settings = get_settings()
    from sqlalchemy.engine import make_url

    name = make_url(settings.database_url).database or ""
    if not name.endswith("_test"):
        raise RuntimeError("Tests delete all tables: DATABASE_URL must name a dedicated database ending in _test")
    engine = create_engine(settings.sync_database_url)
    from app.models import Base

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        from app.core.evidence import EVIDENCE_TABLES, TRIGGER_FUNCTION_SQL, trigger_sql

        conn.execute(text(TRIGGER_FUNCTION_SQL))
        for table in EVIDENCE_TABLES:
            conn.execute(text(trigger_sql(table)))
    engine.dispose()
    yield


@pytest.fixture(scope="session")
async def seeded(database):
    from app.seed import seed_core

    await seed_core()
    return True


@pytest.fixture(scope="session")
def app(database):
    import app.jobs.handlers  # noqa: F401
    import app.services.assistant  # noqa: F401
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.core.ratelimit import limiter

    limiter.reset()
    yield


@pytest.fixture
async def client(app, seeded):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_user(client: httpx.AsyncClient, *, plan: str | None = "assistant", name: str = "Test Teacher") -> dict:
    email = f"t-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1",
                                                          "name": name, "accept_terms": True})
    assert r.status_code == 200, r.text
    data = r.json()
    client.cookies.clear()  # each test user authenticates with its own bearer token
    headers = {"Authorization": f"Bearer {data['token']}"}
    from app.core.db import get_sessionmaker

    if plan == "free":  # end the sign-up trial so the account is on the Free plan
        from sqlalchemy import update

        from app.models import Subscription

        async with get_sessionmaker()() as db:
            await db.execute(update(Subscription).where(Subscription.user_id == uuid.UUID(data["user"]["id"]),
                                                        Subscription.provider == "trial").values(status="canceled"))
            await db.commit()
    elif plan:
        from app.services.billing import set_manual_plan

        async with get_sessionmaker()() as db:
            await set_manual_plan(db, uuid.UUID(data["user"]["id"]), plan, months=1)
    return {"email": email, "headers": headers, "id": data["user"]["id"], "token": data["token"]}


async def make_staff(client: httpx.AsyncClient, admin_role: str = "super_admin") -> dict:
    """A staff account with the given role. Signs in again so the token carries the new permissions."""
    u = await make_user(client, plan=None, name=f"Staff {admin_role}")
    from app.core.db import get_sessionmaker
    from app.models import User

    async with get_sessionmaker()() as db:
        row = await db.get(User, uuid.UUID(u["id"]))
        row.role, row.admin_role = "admin", admin_role
        await db.commit()
    return u


@pytest.fixture
async def teacher(client):
    return await make_user(client)
