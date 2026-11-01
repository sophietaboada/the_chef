"""Game state endpoint: level, XP, streak, quests, badges."""

from __future__ import annotations

from sanic import Blueprint, Request, json

from ..accounts.sessions import login_required
from ..libs.validation import day
from ..profile.service import load_targets
from . import engine

bp = Blueprint("gamification", url_prefix="/api")


@bp.get("/game")
@login_required
async def game(request: Request):
    conn, uid = request.app.ctx.db, request.ctx.user_id
    return json(await engine.summary(conn, uid, day(request.args.get("day")), await load_targets(conn, uid)))
