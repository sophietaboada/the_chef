import itertools

import pytest
from sanic import Sanic

from thechef.app import create_app
from thechef.config import Settings

Sanic.test_mode = True
_ids = itertools.count()


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "test.db"), model="claude-opus-5-5",
                    ai_enabled=False, secure_cookies=False, allow_signup=True)


@pytest.fixture
def app(settings):
    return create_app(settings, name=f"TheChefTest{next(_ids)}")


@pytest.fixture
async def client(app):
    """Logged-in ASGI client."""
    c = app.asgi_client
    _, resp = await c.post("/api/auth/signup", json={"username": "sophie", "password": "correct-horse"})
    assert resp.status == 201, resp.text
    c.cookies = {"thechef_session": resp.cookies["thechef_session"]}
    return c
