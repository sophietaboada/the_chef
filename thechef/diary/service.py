"""The daily food log: entries, totals and what's left of today's targets.

Must not import gamification (gamification depends on the diary, not the other way round).
"""

from __future__ import annotations

from ..libs import db

MEALS = {"breakfast", "lunch", "dinner", "snack"}
MACROS = ("kcal", "protein", "carbs", "fat", "fiber")


def day_totals(entries: list[dict]) -> dict:
    return {k: round(sum(e[k] for e in entries), 1) for k in MACROS}


async def entries_for_day(conn, user_id: int, day: str) -> list[dict]:
    return await db.fetch_all(
        conn, "SELECT * FROM food_log WHERE user_id = ? AND day = ? ORDER BY id", user_id, day
    )


async def day_view(conn, user_id: int, day: str, targets: dict | None) -> dict:
    entries = await entries_for_day(conn, user_id, day)
    totals = day_totals(entries)
    remaining = {k: round(targets[k] - totals[k], 1) for k in MACROS} if targets else None
    return {"day": day, "entries": entries, "totals": totals, "targets": targets, "remaining": remaining}


async def add_entry(conn, user_id: int, day: str, meal: str, name: str, grams: float,
                    macros: dict, food_id: int | None = None) -> dict:
    lid = await db.execute(
        conn,
        """INSERT INTO food_log (user_id, day, meal, food_id, name, grams, kcal, protein, carbs, fat, fiber)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        user_id, day, meal, food_id, name, grams,
        macros["kcal"], macros["protein"], macros["carbs"], macros["fat"], macros.get("fiber") or 0,
    )
    return await db.fetch_one(conn, "SELECT * FROM food_log WHERE id = ?", lid)


async def delete_entry(conn, user_id: int, entry_id: int) -> None:
    await db.execute(conn, "DELETE FROM food_log WHERE id = ? AND user_id = ?", entry_id, user_id)
