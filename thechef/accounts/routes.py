"""Sign-up, login, logout, data export and account deletion."""

from __future__ import annotations

import re

from sanic import Blueprint, Request, json
from sanic.exceptions import BadRequest, Forbidden

from ..libs import db, security
from ..libs.validation import body, text
from . import sessions
from .sessions import login_required

bp = Blueprint("accounts", url_prefix="/api")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
USER_TABLES = ("user_identities", "profiles", "sports", "weight_log", "foods", "food_log", "saved_recipes", "xp_events", "badges")


@bp.post("/auth/signup")
async def signup(request: Request):
    if not request.app.ctx.settings.allow_signup:
        raise Forbidden("Sign-ups are closed.")
    data = body(request)
    username = text(data, "username", 32)
    password = data.get("password") or ""
    if not USERNAME_RE.match(username):
        raise BadRequest("Username: 3-32 letters, numbers, . _ or -")
    if len(password) < 8:
        raise BadRequest("Password must be at least 8 characters.")
    conn = request.app.ctx.db
    if await db.fetch_one(conn, "SELECT 1 FROM users WHERE username = ?", username):
        raise BadRequest("That username is taken.")
    uid = await db.execute(
        conn, "INSERT INTO users (username, password_hash) VALUES (?, ?)", username, security.hash_password(password)
    )
    token = await sessions.create(conn, uid, request.app.ctx.settings.session_days)
    resp = json({"username": username}, status=201)
    sessions.set_cookie(resp, token, request)
    return resp


@bp.get("/auth/options")
async def auth_options(request: Request):
    """Which sign-in options the login screen should show."""
    settings = request.app.ctx.settings
    return json({"google": settings.google_enabled, "signup": settings.allow_signup})


@bp.post("/auth/login")
async def login(request: Request):
    data = body(request)
    conn = request.app.ctx.db
    user = await db.fetch_one(conn, "SELECT * FROM users WHERE username = ?", str(data.get("username", "")))
    if not user or not security.verify_password(str(data.get("password", "")), user["password_hash"]):
        raise BadRequest("Wrong username or password.")
    token = await sessions.create(conn, user["id"], request.app.ctx.settings.session_days)
    resp = json({"username": user["username"]})
    sessions.set_cookie(resp, token, request)
    return resp


@bp.post("/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(sessions.COOKIE)
    if token:
        await sessions.destroy(request.app.ctx.db, token)
    resp = json({"ok": True})
    sessions.clear_cookie(resp)
    return resp


@bp.get("/me")
@login_required
async def me(request: Request):
    conn, uid = request.app.ctx.db, request.ctx.user_id
    user = await db.fetch_one(conn, "SELECT username, created_at, password_hash != '' AS has_password FROM users WHERE id = ?", uid)
    user["has_password"] = bool(user["has_password"])
    has_profile = bool(await db.fetch_one(conn, "SELECT 1 FROM profiles WHERE user_id = ?", uid))
    return json({
        **user,
        "has_profile": has_profile,
        "ai_enabled": request.app.ctx.llm is not None,
        "spoonacular_enabled": bool(request.app.ctx.settings.spoonacular_key),
    })


@bp.get("/me/export")
@login_required
async def export(request: Request):
    """Everything stored about you, as a JSON download."""
    conn, uid = request.app.ctx.db, request.ctx.user_id
    out = {"user": await db.fetch_one(conn, "SELECT username, created_at FROM users WHERE id = ?", uid)}
    for table in USER_TABLES:
        out[table] = await db.fetch_all(conn, f"SELECT * FROM {table} WHERE user_id = ?", uid)
    return json(out, headers={"Content-Disposition": 'attachment; filename="thechef-export.json"'})


@bp.delete("/me")
@login_required
async def delete_account(request: Request):
    data = body(request)
    conn, uid = request.app.ctx.db, request.ctx.user_id
    user = await db.fetch_one(conn, "SELECT username, password_hash FROM users WHERE id = ?", uid)
    if user["password_hash"]:
        if not security.verify_password(str(data.get("password", "")), user["password_hash"]):
            raise BadRequest("Password is incorrect.")
    elif str(data.get("username", "")).strip().lower() != user["username"].lower():
        # Accounts created with Google have no password: confirm by typing the username instead.
        raise BadRequest("Type your username to confirm.")
    await db.execute(conn, "DELETE FROM users WHERE id = ?", uid)  # cascades to all user data
    resp = json({"deleted": True})
    sessions.clear_cookie(resp)
    return resp
