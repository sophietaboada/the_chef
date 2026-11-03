"""Profile (body + job), sports and weight endpoints."""

from __future__ import annotations

from datetime import date

from sanic import Blueprint, Request, json

from .. import nutrition
from ..accounts.sessions import login_required
from ..gamification import engine as game
from ..gamification.rules import XP
from ..libs import db
from ..libs.validation import body, choice, day, num, text
from . import service

bp = Blueprint("profile", url_prefix="/api")


@bp.get("/profile")
@login_required
async def get_profile(request: Request):
    return json(await service.load(request.app.ctx.db, request.ctx.user_id))


@bp.put("/profile")
@login_required
async def put_profile(request: Request):
    data = body(request)
    this_year = date.today().year
    values = {
        "first_name": text(data, "first_name", 40),
        "sex": choice(data, "sex", nutrition.SEXES),
        "birth_year": int(num(data, "birth_year", this_year - 100, this_year - 13)),
        "height_cm": num(data, "height_cm", 100, 250),
        "weight_kg": num(data, "weight_kg", 30, 300),
        "job_activity": choice(data, "job_activity", set(nutrition.JOB_FACTORS)),
        "goal": choice(data, "goal", nutrition.GOALS),
    }
    conn, uid = request.app.ctx.db, request.ctx.user_id
    await service.save(conn, uid, values)
    today = date.today().isoformat()
    weigh_ins = await service.record_weight(conn, uid, today, values["weight_kg"])
    news = await game.give(conn, uid, "profile", today, XP["profile"], "Set up your profile")
    # Saving "About you" is also how you log your weight (once a day earns weigh-in XP).
    news += await game.give(conn, uid, f"weigh_in:{today}", today, XP["weigh_in"], "Weigh-in logged")
    if weigh_ins >= 10:
        news += await game.unlock(conn, uid, "weigh_in_10")
    return json({**await service.load(conn, uid), "news": news})


@bp.post("/sports")
@login_required
async def add_sport(request: Request):
    data = body(request)
    conn = request.app.ctx.db
    sid = await db.execute(
        conn,
        "INSERT INTO sports (user_id, name, sessions_per_week, minutes_per_session, intensity) VALUES (?, ?, ?, ?, ?)",
        request.ctx.user_id,
        text(data, "name", 60),
        num(data, "sessions_per_week", 0.25, 21),
        num(data, "minutes_per_session", 5, 600),
        choice(data, "intensity", set(nutrition.INTENSITY_METS)),
    )
    return json(await db.fetch_one(conn, "SELECT * FROM sports WHERE id = ?", sid), status=201)


@bp.delete("/sports/<sport_id:int>")
@login_required
async def delete_sport(request: Request, sport_id: int):
    await db.execute(
        request.app.ctx.db, "DELETE FROM sports WHERE id = ? AND user_id = ?", sport_id, request.ctx.user_id
    )
    return json({"ok": True})


@bp.get("/weight")
@login_required
async def weight_history(request: Request):
    rows = await db.fetch_all(
        request.app.ctx.db,
        "SELECT day, weight_kg FROM weight_log WHERE user_id = ? ORDER BY day DESC LIMIT 90",
        request.ctx.user_id,
    )
    return json(list(reversed(rows)))


@bp.post("/weight")
@login_required
async def log_weight(request: Request):
    data = body(request)
    d = day(data.get("day"))
    conn, uid = request.app.ctx.db, request.ctx.user_id
    count = await service.record_weight(conn, uid, d, num(data, "weight_kg", 30, 300))
    news = await game.give(conn, uid, f"weigh_in:{d}", d, XP["weigh_in"], "Weigh-in logged")
    if count >= 10:
        news += await game.unlock(conn, uid, "weigh_in_10")
    return json({"ok": True, "news": news})
