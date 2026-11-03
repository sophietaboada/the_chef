import base64
import json
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import pytest

from thechef.accounts import google
from thechef.app import create_app

CLIENT_ID = "test-client.apps.googleusercontent.com"


def make_id_token(**claims) -> str:
    body = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "1234567890",
            "email": "ada.lovelace@gmail.com", "email_verified": True, "exp": time.time() + 600, **claims}
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{enc({'alg': 'RS256'})}.{enc(body)}.signature"


@pytest.fixture
def gapp(settings):
    s = replace(settings, public_url="https://chef.example.com",
                google_client_id=CLIENT_ID, google_client_secret="secret")
    return create_app(s, name=f"TheChefGoogle{id(s)}")


@pytest.fixture
def fake_google(monkeypatch):
    """Replace Google's token endpoint. Set fake_google['id_token'] to control the response."""
    state = {"id_token": make_id_token(), "requests": []}

    async def fake_exchange(http, form):
        state["requests"].append(form)
        return {"id_token": state["id_token"]}

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    return state


async def sign_in(app):
    """Run /start then /callback like a browser would. Returns (client, callback response);
    the client keeps the session cookie when sign-in succeeded."""
    c = app.asgi_client
    _, resp = await c.get("/api/auth/google/start", follow_redirects=False)
    assert resp.status == 302
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["redirect_uri"] == ["https://chef.example.com/api/auth/google/callback"]
    assert query["code_challenge_method"] == ["S256"]
    c.cookies = {google.STATE_COOKIE: resp.cookies[google.STATE_COOKIE]}
    _, resp = await c.get(f"/api/auth/google/callback?code=abc&state={query['state'][0]}", follow_redirects=False)
    if "thechef_session" in resp.cookies:
        c.cookies = {"thechef_session": resp.cookies["thechef_session"]}
    return c, resp


async def test_options_hide_google_when_not_configured(app):
    _, resp = await app.asgi_client.get("/api/auth/options")
    assert resp.json == {"google": False, "signup": True}
    _, resp = await app.asgi_client.get("/api/auth/google/start", follow_redirects=False)
    assert resp.status == 404


async def test_google_sign_in_creates_then_reuses_account(gapp, fake_google):
    _, resp = await gapp.asgi_client.get("/api/auth/options")
    assert resp.json["google"] is True

    c, resp = await sign_in(gapp)
    assert resp.status == 302 and resp.headers["location"] == "/"
    assert fake_google["requests"][0]["code_verifier"]
    _, me = await c.get("/api/me")
    assert me.json["username"] == "ada.lovelace"
    assert me.json["has_password"] is False

    # Same Google account again -> same user (a new one would be "ada.lovelace2").
    c, _ = await sign_in(gapp)
    _, me = await c.get("/api/me")
    assert me.json["username"] == "ada.lovelace"


async def test_google_user_cannot_log_in_with_empty_password(gapp, fake_google):
    await sign_in(gapp)
    for pw in ("", "anything-at-all"):
        _, resp = await gapp.asgi_client.post("/api/auth/login", json={"username": "ada.lovelace", "password": pw})
        assert resp.status == 400


async def test_username_collision_gets_suffix(gapp, fake_google):
    _, resp = await gapp.asgi_client.post("/api/auth/signup", json={"username": "ada.lovelace", "password": "correct-horse"})
    assert resp.status == 201
    c, _ = await sign_in(gapp)
    _, me = await c.get("/api/me")
    assert me.json["username"] == "ada.lovelace2"


async def test_callback_rejects_wrong_state(gapp, fake_google):
    c = gapp.asgi_client
    _, resp = await c.get("/api/auth/google/start", follow_redirects=False)
    c.cookies = {google.STATE_COOKIE: resp.cookies[google.STATE_COOKIE]}
    _, resp = await c.get("/api/auth/google/callback?code=abc&state=forged", follow_redirects=False)
    assert resp.headers["location"].startswith("/?auth_error=")
    assert "thechef_session" not in resp.cookies
    assert fake_google["requests"] == []


async def test_callback_rejects_token_for_other_app(gapp, fake_google):
    fake_google["id_token"] = make_id_token(aud="someone-else")
    _, resp = await sign_in(gapp)
    assert resp.headers["location"].startswith("/?auth_error=")
    assert "thechef_session" not in resp.cookies


async def test_closed_signups_block_new_google_users(settings, fake_google):
    s = replace(settings, allow_signup=False, public_url="https://chef.example.com",
                google_client_id=CLIENT_ID, google_client_secret="secret")
    _, resp = await sign_in(create_app(s, name="TheChefGoogleClosed"))
    assert resp.headers["location"] == "/?auth_error=Sign-ups%20are%20closed."
    assert "thechef_session" not in resp.cookies


async def test_google_user_deletes_account_by_typing_username(gapp, fake_google):
    c, _ = await sign_in(gapp)
    _, resp = await c.request("DELETE", "/api/me", json={"username": "someone"})
    assert resp.status == 400
    _, resp = await c.request("DELETE", "/api/me", json={"username": "Ada.Lovelace"})
    assert resp.status == 200
    # The Google link went with it: signing in again creates a fresh account.
    c, _ = await sign_in(gapp)
    _, me = await c.get("/api/me")
    assert me.json["username"] == "ada.lovelace"
    assert me.json["has_password"] is False


def test_parse_id_token_rejects_bad_tokens():
    with pytest.raises(ValueError):
        google.parse_id_token(make_id_token(exp=time.time() - 1), CLIENT_ID)
    with pytest.raises(ValueError):
        google.parse_id_token("not-a-token", CLIENT_ID)
    with pytest.raises(ValueError):
        google.parse_id_token(make_id_token(iss="https://evil.example"), CLIENT_ID)
    assert google.parse_id_token(make_id_token(), CLIENT_ID)["sub"] == "1234567890"
