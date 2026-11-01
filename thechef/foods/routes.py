"""Saved foods and the four ways to look one up: manual, barcode, label photo, AI estimate.

Lookups return a *draft*; nothing is saved until the user confirms it via POST /api/foods.
"""

from __future__ import annotations

from datetime import date

from sanic import Blueprint, Request, json
from sanic.exceptions import BadRequest, NotFound

from ..accounts.sessions import login_required
from ..gamification import engine as game
from ..gamification.rules import XP
from ..libs import db
from ..libs.llm import LLMError
from ..libs.validation import body, image, num, text
from ..libs.web import ServiceUnavailable, require_llm
from . import ai, openfoodfacts

bp = Blueprint("foods", url_prefix="/api/foods")

SOURCES = {"manual", "barcode", "label_photo", "ai_estimate"}
SOURCE_BADGES = {"barcode": "scanner", "label_photo": "label_reader", "ai_estimate": "food_detective"}


def food_values(data: dict) -> dict:
    barcode = data.get("barcode")
    if barcode and not openfoodfacts.valid_barcode(str(barcode)):
        raise BadRequest("Invalid barcode.")
    return {
        "name": text(data, "name", 120),
        "brand": text(data, "brand", 80, required=False),
        "barcode": str(barcode) if barcode else None,
        "source": data.get("source") if data.get("source") in SOURCES else "manual",
        "kcal": num(data, "kcal", 0, 900),
        "protein": num(data, "protein", 0, 100),
        "carbs": num(data, "carbs", 0, 100),
        "fat": num(data, "fat", 0, 100),
        "fiber": num(data, "fiber", 0, 100, required=False),
        "sugar": num(data, "sugar", 0, 100, required=False),
        "serving_g": num(data, "serving_g", 1, 2000, required=False),
    }


@bp.get("/")
@login_required
async def list_foods(request: Request):
    q = f"%{request.args.get('q', '').strip()}%"
    rows = await db.fetch_all(
        request.app.ctx.db,
        "SELECT * FROM foods WHERE user_id = ? AND (name LIKE ? OR brand LIKE ?) ORDER BY name LIMIT 100",
        request.ctx.user_id, q, q,
    )
    return json(rows)


@bp.post("/")
@login_required
async def create_food(request: Request):
    values = food_values(body(request))
    conn, uid = request.app.ctx.db, request.ctx.user_id
    fid = await db.execute(
        conn,
        """INSERT INTO foods (user_id, name, brand, barcode, source, kcal, protein, carbs, fat, fiber, sugar, serving_g)
           VALUES (:uid, :name, :brand, :barcode, :source, :kcal, :protein, :carbs, :fat, :fiber, :sugar, :serving_g)""",
        {"uid": uid, **values},
    )
    news = await game.give(conn, uid, f"food:{fid}", date.today().isoformat(), XP["new_food"], "New food added")
    if values["source"] in SOURCE_BADGES:
        news += await game.unlock(conn, uid, SOURCE_BADGES[values["source"]])
    food = await db.fetch_one(conn, "SELECT * FROM foods WHERE id = ?", fid)
    return json({**food, "news": news}, status=201)


@bp.delete("/<food_id:int>")
@login_required
async def delete_food(request: Request, food_id: int):
    await db.execute(
        request.app.ctx.db, "DELETE FROM foods WHERE id = ? AND user_id = ?", food_id, request.ctx.user_id
    )
    return json({"ok": True})


@bp.get("/barcode/<code>")
@login_required
async def barcode_lookup(request: Request, code: str):
    if not openfoodfacts.valid_barcode(code):
        raise BadRequest("Barcodes are 6-14 digits.")
    saved = await db.fetch_one(
        request.app.ctx.db, "SELECT * FROM foods WHERE user_id = ? AND barcode = ? ORDER BY id DESC",
        request.ctx.user_id, code,
    )
    if saved:
        return json({**saved, "saved": True, "complete": True})
    try:
        product = await openfoodfacts.lookup(code, request.app.ctx.http)
    except openfoodfacts.LookupFailed as e:
        raise ServiceUnavailable(str(e))
    if not product:
        raise NotFound("Product not found. Try a photo of the label or add it manually.")
    return json({**product, "saved": False})


@bp.post("/label")
@login_required
async def read_label(request: Request):
    llm = require_llm(request)
    data = body(request)
    img, media_type = image(data)
    try:
        return json(await ai.read_label(llm, img, media_type, text(data, "hint", 200, required=False) or ""))
    except LLMError as e:
        raise ServiceUnavailable(str(e))


@bp.post("/estimate")
@login_required
async def estimate_food(request: Request):
    llm = require_llm(request)
    try:
        return json(await ai.estimate(llm, text(body(request), "description", 500)))
    except LLMError as e:
        raise ServiceUnavailable(str(e))
