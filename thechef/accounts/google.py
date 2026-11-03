"""Sign in with Google: OAuth 2.0 authorization-code flow with PKCE.

Only Google's stable account id (`sub`) and the email address are stored (in user_identities).
The ID token comes straight from Google's token endpoint over TLS, so its claims can be trusted
without verifying the signature (see Google's OpenID Connect docs); we still check aud/iss/exp.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, urlencode

import httpx
from sanic import Blueprint, Request, redirect
from sanic.exceptions import NotFound

from ..libs import db, security
from . import sessions

bp = Blueprint("google_auth", url_prefix="/api/auth/google")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
STATE_COOKIE = "thechef_oauth"
STATE_PATH = "/api/auth/google"


def _redirect_uri(settings) -> str:
    return f"{settings.public_url}/api/auth/google/callback"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@bp.get("/start")
async def start(request: Request):
    settings = request.app.ctx.settings
    if not settings.google_enabled:
        raise NotFound("Google sign-in is not configured.")
    state, verifier = security.new_token(), security.new_token()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _redirect_uri(settings),
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    resp = redirect(f"{AUTH_URL}?{urlencode(params)}")
    # Tokens are URL-safe base64, which never contains ".".
    resp.add_cookie(
        STATE_COOKIE, f"{state}.{verifier}",
        httponly=True, samesite="Lax", secure=settings.secure_cookies, max_age=600, path=STATE_PATH,
    )
    return resp


def _done(location: str):
    resp = redirect(location)
    resp.delete_cookie(STATE_COOKIE, path=STATE_PATH)
    return resp


def _fail(message: str):
    return _done("/?auth_error=" + quote(message))


def parse_id_token(id_token: str, client_id: str) -> dict:
    """Decode the ID token's claims and check they were issued by Google for this app."""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise ValueError("Malformed ID token") from exc
    if claims.get("aud") != client_id or claims.get("iss") not in ISSUERS:
        raise ValueError("ID token is not for this app")
    if float(claims.get("exp", 0)) < time.time() or not claims.get("sub"):
        raise ValueError("ID token expired or has no subject")
    return claims


async def _free_username(conn, email: str | None) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "", (email or "").split("@")[0])[:28]
    if len(base) < 3:
        base = "chef"
    candidate, n = base, 1
    while await db.fetch_one(conn, "SELECT 1 FROM users WHERE username = ?", candidate):
        n += 1
        candidate = f"{base}{n}"
    return candidate


async def user_for_google(conn, claims: dict, allow_signup: bool) -> int | None:
    """Existing user linked to this Google account, or a new one. None if sign-ups are closed."""
    row = await db.fetch_one(
        conn, "SELECT user_id FROM user_identities WHERE provider = 'google' AND subject = ?", claims["sub"]
    )
    if row:
        return row["user_id"]
    if not allow_signup:
        return None
    email = claims.get("email") if claims.get("email_verified") else None
    username = await _free_username(conn, email)
    cur = await conn.execute("INSERT INTO users (username, password_hash) VALUES (?, '')", (username,))
    uid = cur.lastrowid
    await conn.execute(
        "INSERT INTO user_identities (provider, subject, user_id, email) VALUES ('google', ?, ?, ?)",
        (claims["sub"], uid, email),
    )
    await conn.commit()
    return uid


async def exchange_code(http: httpx.AsyncClient, form: dict) -> dict:
    """POST to Google's token endpoint and return its JSON (contains `id_token`)."""
    resp = await http.post(TOKEN_URL, data=form)
    resp.raise_for_status()
    return resp.json()


@bp.get("/callback")
async def callback(request: Request):
    settings = request.app.ctx.settings
    if not settings.google_enabled:
        raise NotFound("Google sign-in is not configured.")
    if request.args.get("error"):
        return _fail("Google sign-in was cancelled.")
    state, _, verifier = request.cookies.get(STATE_COOKIE, "").partition(".")
    if not state or not verifier or not hmac.compare_digest(state, request.args.get("state", "")):
        return _fail("Sign-in expired. Please try again.")
    try:
        tokens = await exchange_code(request.app.ctx.http, {
            "code": request.args.get("code", ""),
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": _redirect_uri(settings),
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        })
        claims = parse_id_token(tokens["id_token"], settings.google_client_id)
    except (httpx.HTTPError, KeyError, ValueError):
        return _fail("Couldn't sign in with Google. Please try again.")

    conn = request.app.ctx.db
    uid = await user_for_google(conn, claims, settings.allow_signup)
    if uid is None:
        return _fail("Sign-ups are closed.")
    token = await sessions.create(conn, uid, settings.session_days)
    out = _done("/")
    sessions.set_cookie(out, token, request)
    return out
