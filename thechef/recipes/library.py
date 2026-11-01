"""A user's saved recipe book (from AI suggestions or online sources)."""

from __future__ import annotations

import json

from ..libs import db
from .search import to_public

SOURCES = {"ai", "spoonacular", "mealdb"}


def _row_to_recipe(row: dict) -> dict:
    return to_public({
        "id": f"u{row['id']}",
        "saved_id": row["id"],
        "source": row["source"],
        "external_id": row["external_id"],
        "title": row["title"],
        "minutes": row["minutes"],
        "servings": row["servings"],
        "tags": json.loads(row["tags"]),
        "ingredients": json.loads(row["ingredients"]),
        "steps": json.loads(row["steps"]),
        "kcal": row["kcal"],
        "protein": row["protein"],
        "carbs": row["carbs"],
        "fat": row["fat"],
        "macros_estimated": bool(row["macros_estimated"]),
        "image_url": row["image_url"],
        "source_url": row["source_url"],
    })


async def list_saved(conn, user_id: int) -> list[dict]:
    rows = await db.fetch_all(conn, "SELECT * FROM saved_recipes WHERE user_id = ? ORDER BY id DESC", user_id)
    return [_row_to_recipe(r) for r in rows]


async def get_saved(conn, user_id: int, saved_id: int) -> dict | None:
    row = await db.fetch_one(conn, "SELECT * FROM saved_recipes WHERE id = ? AND user_id = ?", saved_id, user_id)
    return _row_to_recipe(row) if row else None


async def save(conn, user_id: int, r: dict) -> tuple[dict, bool]:
    """Save a (validated) recipe. Returns (recipe, created). Re-saving the same one is a no-op."""
    external_id = r.get("external_id") or r["title"].lower()[:120]
    existing = await db.fetch_one(
        conn, "SELECT id FROM saved_recipes WHERE user_id = ? AND source = ? AND external_id = ?",
        user_id, r["source"], external_id,
    )
    if existing:
        return await get_saved(conn, user_id, existing["id"]), False
    sid = await db.execute(
        conn,
        """INSERT INTO saved_recipes (user_id, source, external_id, title, minutes, servings, tags, ingredients,
             steps, kcal, protein, carbs, fat, macros_estimated, image_url, source_url)
           VALUES (:uid, :source, :external_id, :title, :minutes, :servings, :tags, :ingredients, :steps,
             :kcal, :protein, :carbs, :fat, :macros_estimated, :image_url, :source_url)""",
        {
            "uid": user_id, "source": r["source"], "external_id": external_id, "title": r["title"],
            "minutes": r["minutes"], "servings": r["servings"],
            "tags": json.dumps(r["tags"]), "ingredients": json.dumps(r["ingredients"]),
            "steps": json.dumps(r["steps"]), "kcal": r["kcal"], "protein": r["protein"],
            "carbs": r["carbs"], "fat": r["fat"], "macros_estimated": int(bool(r.get("macros_estimated"))),
            "image_url": r.get("image_url"), "source_url": r.get("source_url"),
        },
    )
    return await get_saved(conn, user_id, sid), True


async def delete(conn, user_id: int, saved_id: int) -> None:
    await db.execute(conn, "DELETE FROM saved_recipes WHERE id = ? AND user_id = ?", saved_id, user_id)


async def count(conn, user_id: int) -> int:
    row = await db.fetch_one(conn, "SELECT COUNT(*) AS n FROM saved_recipes WHERE user_id = ?", user_id)
    return row["n"]
