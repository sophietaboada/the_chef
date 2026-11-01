"""Recipe search (built-in + saved), pantry matching, online search, AI ideas,
the saved recipe book, and 'I cooked this' logging."""

from __future__ import annotations

import re

from sanic import Blueprint, Request, json
from sanic.exceptions import BadRequest, NotFound

from ..accounts.sessions import login_required
from ..diary import service as diary
from ..gamification import engine as game
from ..gamification.rules import XP
from ..libs.llm import LLMError
from ..libs.validation import body, choice, day, num, text
from ..libs.web import ServiceUnavailable, require_llm
from ..profile.service import load_targets
from . import ai, library, online, search

bp = Blueprint("recipes", url_prefix="/api/recipes")


# ---------- helpers ----------

def ingredient_list(value) -> list[str]:
    items = value or []
    if isinstance(items, str):
        items = re.split(r"[,\n]", items)
    if not isinstance(items, list):
        raise BadRequest("'ingredients' must be a list.")
    return [str(i).strip()[:60] for i in items if str(i).strip()][:40]


def opt_num(args, key: str) -> float | None:
    v = args.get(key)
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        raise BadRequest(f"'{key}' must be a number.")


async def all_recipes(request: Request) -> list[dict]:
    """Built-in catalog + this user's saved recipe book."""
    return search.BUILT_IN + await library.list_saved(request.app.ctx.db, request.ctx.user_id)


def recipe_from_body(r: dict) -> dict:
    """Validate a recipe sent by the client (AI or online result) before saving/cooking it."""
    if not isinstance(r, dict):
        raise BadRequest("'recipe' must be an object.")
    source = r.get("source")
    if source not in library.SOURCES:
        raise BadRequest("Only AI or online recipes can be saved.")

    def str_list(key, max_items, max_len):
        v = r.get(key) or []
        if not isinstance(v, list):
            raise BadRequest(f"'{key}' must be a list.")
        return [str(x)[:max_len] for x in v][:max_items]

    ingredients = []
    for i in (r.get("ingredients") or [])[:40]:
        if isinstance(i, dict) and str(i.get("name", "")).strip():
            ingredients.append({"name": str(i["name"])[:80], "amount": str(i.get("amount") or "")[:80]})
    def https_url(key):  # only allow https links (no javascript: etc.)
        v = str(r.get(key) or "")[:500]
        return v if v.startswith("https://") else None

    return {
        "source": source,
        "external_id": str(r.get("external_id") or "")[:120] or None,
        "title": text(r, "title", 160),
        "minutes": int(num(r, "minutes", 0, 1440, required=False) or 0) or None,
        "servings": num(r, "servings", 0.5, 50, required=False) or 1,
        "tags": str_list("tags", 12, 40),
        "ingredients": ingredients,
        "steps": str_list("steps", 40, 1000),
        "kcal": num(r, "kcal", 0, 3000),
        "protein": num(r, "protein", 0, 300),
        "carbs": num(r, "carbs", 0, 500),
        "fat": num(r, "fat", 0, 300),
        "macros_estimated": bool(r.get("macros_estimated")),
        "image_url": https_url("image_url"),
        "source_url": https_url("source_url"),
    }


# ---------- search ----------

@bp.get("/")
@login_required
async def search_recipes(request: Request):
    a = request.args
    return json(search.search(await all_recipes(request), a.get("q", ""), opt_num(a, "max_kcal"),
                              opt_num(a, "min_protein"), a.get("tag") or None))


@bp.post("/pantry")
@login_required
async def pantry_recipes(request: Request):
    items = ingredient_list(body(request).get("ingredients"))
    if not items:
        raise BadRequest("List at least one ingredient.")
    results = search.by_pantry(await all_recipes(request), items)
    news = await game.unlock(request.app.ctx.db, request.ctx.user_id, "pantry_raider") if results else []
    return json({"recipes": results, "news": news})


@bp.get("/online")
@login_required
async def online_recipes(request: Request):
    """?source=spoonacular|mealdb&q=&ingredients=a,b&max_kcal=&min_protein="""
    a = request.args
    source = a.get("source", "spoonacular")
    query = (a.get("q") or "").strip()[:100]
    ingredients = ingredient_list(a.get("ingredients", ""))[:8]
    max_kcal, min_protein = opt_num(a, "max_kcal"), opt_num(a, "min_protein")
    http = request.app.ctx.http
    note = None
    try:
        if source == "spoonacular":
            key = request.app.ctx.settings.spoonacular_key
            if not key:
                raise ServiceUnavailable("Spoonacular is off. Set SPOONACULAR_API_KEY to enable it.")
            results = await online.spoonacular_search(
                http, key, query=query, ingredients=ingredients, max_kcal=max_kcal, min_protein=min_protein
            )
        elif source == "mealdb":
            results = await online.mealdb_search(http, query=query, ingredients=ingredients)
            llm = request.app.ctx.llm
            if llm and results:
                try:
                    await ai.estimate_macros(llm, results)
                    note = "Macros for these recipes are AI estimates."
                except LLMError as e:
                    note = f"Couldn't estimate macros: {e}"
            else:
                note = "TheMealDB has no nutrition data; enable AI to estimate macros."
            results = [search.to_public(r) if r["kcal"] is not None else r for r in results]
            # Only filter on macros we actually have.
            results = [
                r for r in results
                if r["kcal"] is None or (
                    (max_kcal is None or r["kcal"] <= max_kcal)
                    and (min_protein is None or r["protein"] >= min_protein)
                )
            ]
            results.sort(key=lambda r: r.get("protein_per_100kcal") or 0, reverse=True)
        else:
            raise BadRequest("source must be 'spoonacular' or 'mealdb'.")
    except online.OnlineError as e:
        raise ServiceUnavailable(str(e))

    if pantry := ingredients:
        results = [  # annotate have/missing like the pantry view
            {**r, **{k: v for k, v in (search.by_pantry([r], pantry, max_missing=99) or [{}])[0].items()
                     if k in ("have", "missing", "match")}}
            for r in results
        ]
    news = await game.unlock(request.app.ctx.db, request.ctx.user_id, "explorer") if results else []
    return json({"recipes": results, "note": note, "news": news})


@bp.post("/ai")
@login_required
async def ai_recipes(request: Request):
    llm = require_llm(request)
    data = body(request)
    budget = None
    if data.get("use_remaining"):
        conn, uid = request.app.ctx.db, request.ctx.user_id
        view = await diary.day_view(conn, uid, day(data.get("day")), await load_targets(conn, uid))
        if view["remaining"]:
            r = view["remaining"]
            budget = {"kcal": max(150, round(r["kcal"])), "protein": max(0, round(r["protein"]))}
    try:
        results = await ai.suggest(llm, ingredient_list(data.get("ingredients")),
                                   text(data, "preferences", 200, required=False) or "", budget)
    except LLMError as e:
        raise ServiceUnavailable(str(e))
    return json({"recipes": results, "budget": budget})


# ---------- saved recipe book ----------

@bp.get("/saved")
@login_required
async def list_saved(request: Request):
    return json(await library.list_saved(request.app.ctx.db, request.ctx.user_id))


@bp.post("/saved")
@login_required
async def save_recipe(request: Request):
    recipe = recipe_from_body(body(request).get("recipe"))
    conn, uid = request.app.ctx.db, request.ctx.user_id
    saved, created = await library.save(conn, uid, recipe)
    news = []
    if created and await library.count(conn, uid) >= 5:
        news += await game.unlock(conn, uid, "collector")
    return json({**saved, "news": news, "created": created}, status=201 if created else 200)


@bp.delete("/saved/<saved_id:int>")
@login_required
async def delete_saved(request: Request, saved_id: int):
    await library.delete(request.app.ctx.db, request.ctx.user_id, saved_id)
    return json({"ok": True})


# ---------- cooking ----------

@bp.post("/cook")
@login_required
async def cook_recipe(request: Request):
    """Log servings of a recipe: by `recipe_id` (built-in id or 'u<saved id>'), or inline `recipe`."""
    data = body(request)
    d = day(data.get("day"))
    meal = choice(data, "meal", diary.MEALS)
    servings = num(data, "servings", 0.25, 10)
    conn, uid = request.app.ctx.db, request.ctx.user_id

    rid = str(data.get("recipe_id") or "")
    if re.fullmatch(r"u\d+", rid):
        recipe = await library.get_saved(conn, uid, int(rid[1:]))
    elif rid:
        recipe = search.get_built_in(rid)
    else:
        recipe = recipe_from_body(data.get("recipe"))
        slug = recipe["external_id"] or re.sub(r"\W+", "-", recipe["title"].lower())[:40]
        rid = f"{recipe['source']}:{slug}"
    if not recipe:
        raise NotFound("Recipe not found.")

    macros = {k: round(recipe[k] * servings, 1) for k in ("kcal", "protein", "carbs", "fat")}
    entry = await diary.add_entry(conn, uid, d, meal, f"{recipe['title']} ×{servings:g}", 0, macros)

    news = await game.give(conn, uid, f"cook:{rid}:{d}", d, XP["cook_recipe"], f"Cooked {recipe['title']}")
    if await game.count_events(conn, uid, "cook:%") >= 5:
        news += await game.unlock(conn, uid, "home_cook")
    news += await game.after_log_change(conn, uid, d)
    return json({"log_id": entry["id"], "news": news}, status=201)
