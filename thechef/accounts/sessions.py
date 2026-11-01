"""Cookie sessions and the `login_required` decorator used by every other domain's routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps

from sanic import Request
from sanic.exceptions import Unauthorized

from ..libs import db, security

COOKIE = "thechef_session"


async def create(conn, user_id: int, days: int) -> str:
    token = security.new_token()
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    await db.execute(
        conn,
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        security.token_hash(token), user_id, expires.isoformat(),
    )
    return token


async def destroy(conn, token: str) -> None:
    await db.execute(conn, "DELETE FROM sessions WHERE token_hash = ?", security.token_hash(token))


async def user_for_token(conn, token: str | None) -> int | None:
    if not token:
        return None
    row = await db.fetch_one(
        conn, "SELECT user_id, expires_at FROM sessions WHERE token_hash = ?", security.token_hash(token)
    )
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        await destroy(conn, token)
        return None
    return row["user_id"]


def set_cookie(response, token: str, request: Request) -> None:
    settings = request.app.ctx.settings
    response.add_cookie(
        COOKIE, token,
        httponly=True, samesite="Lax", secure=settings.secure_cookies,
        max_age=settings.session_days * 86400, path="/",
    )


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path="/")


def login_required(handler):
    @wraps(handler)
    async def wrapper(request: Request, *args, **kwargs):
        user_id = await user_for_token(request.app.ctx.db, request.cookies.get(COOKIE))
        if user_id is None:
            raise Unauthorized("Please log in.")
        request.ctx.user_id = user_id
        return await handler(request, *args, **kwargs)

    return wrapper
