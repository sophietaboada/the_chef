"""Daily food log endpoints."""

from __future__ import annotations

from sanic import Blueprint, Request, json
from sanic.exceptions import NotFound

from .. import nutrition
from ..accounts.sessions import login_required
from ..gamification import engine as game
from ..libs import db
from ..libs.validation import body, choice, day, num, text
from ..profile.service import load_targets
from . import service

bp = Blueprint("diary", url_prefix="/api")


@bp.get("/log")
@login_required
async def get_log(request: Request):
    conn, uid = request.app.ctx.db, request.ctx.user_id
    return json(await service.day_view(conn, uid, day(request.args.get("day")), await load_targets(conn, uid)))


@bp.post("/log")
@login_required
async def add_log(request: Request):
    """Either {food_id, grams} for a saved food, or a quick add with macros for the whole portion."""
    data = body(request)
    d = day(data.get("day"))
    meal = choice(data, "meal", service.MEALS)
    conn, uid = request.app.ctx.db, request.ctx.user_id

    if data.get("food_id") is not None:
        food = await db.fetch_one(conn, "SELECT * FROM foods WHERE id = ? AND user_id = ?", int(data["food_id"]), uid)
        if not food:
            raise NotFound("Food not found.")
        grams = num(data, "grams", 1, 5000)
        entry = await service.add_entry(conn, uid, d, meal, food["name"], grams, nutrition.portion(food, grams), food["id"])
    else:
        macros = {
            "kcal": num(data, "kcal", 0, 5000),
            "protein": num(data, "protein", 0, 500),
            "carbs": num(data, "carbs", 0, 1000),
            "fat": num(data, "fat", 0, 500),
            "fiber": num(data, "fiber", 0, 200, required=False),
        }
        grams = num(data, "grams", 0, 5000, required=False) or 0
        entry = await service.add_entry(conn, uid, d, meal, text(data, "name", 120), grams, macros)

    news = await game.after_log_change(conn, uid, d)
    return json({**entry, "news": news}, status=201)


@bp.delete("/log/<entry_id:int>")
@login_required
async def delete_log(request: Request, entry_id: int):
    await service.delete_entry(request.app.ctx.db, request.ctx.user_id, entry_id)
    return json({"ok": True})
