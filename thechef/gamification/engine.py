"""XP ledger, levels, streaks, badges and daily quests.

All awards go through `award()`, which is idempotent per key, so re-evaluating a day never
double-counts. Call `evaluate_day()` after anything that changes a day's food log.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

from ..diary.service import day_totals
from ..libs import db
from ..profile.service import load_targets
from .rules import BADGES, LEVEL_TITLES, QUESTS, VEG_WORDS, XP


# ---------- levels ----------

def xp_for_level(level: int) -> int:
    """Cumulative XP needed to reach `level` (level 1 = 0 XP). Grows quadratically."""
    n = level - 1
    return 50 * n * (n + 1)


def level_for_xp(xp: int) -> int:
    # Inverse of xp_for_level: 50 n(n+1) <= xp
    n = int((math.sqrt(1 + 4 * xp / 50) - 1) / 2)
    while xp_for_level(n + 2) <= xp:
        n += 1
    while n > 0 and xp_for_level(n + 1) > xp:
        n -= 1
    return n + 1


def level_info(xp: int) -> dict:
    lvl = level_for_xp(xp)
    start, nxt = xp_for_level(lvl), xp_for_level(lvl + 1)
    return {
        "level": lvl,
        "title": LEVEL_TITLES[min(lvl - 1, len(LEVEL_TITLES) - 1)],
        "xp": xp,
        "level_start_xp": start,
        "next_level_xp": nxt,
        "progress": round((xp - start) / (nxt - start), 3),
    }


# ---------- ledger ----------

async def award(conn, user_id: int, key: str, day: str, points: int, label: str) -> bool:
    async with conn.execute(
        "INSERT OR IGNORE INTO xp_events (user_id, key, day, points, label) VALUES (?, ?, ?, ?, ?)",
        (user_id, key, day, points, label),
    ) as cur:
        inserted = cur.rowcount > 0
    await conn.commit()
    return inserted


async def grant_badge(conn, user_id: int, code: str) -> bool:
    async with conn.execute(
        "INSERT OR IGNORE INTO badges (user_id, code) VALUES (?, ?)", (user_id, code)
    ) as cur:
        inserted = cur.rowcount > 0
    await conn.commit()
    return inserted


async def total_xp(conn, user_id: int) -> int:
    row = await db.fetch_one(
        conn, "SELECT COALESCE(SUM(points), 0) AS xp FROM xp_events WHERE user_id = ?", user_id
    )
    return row["xp"]


# ---------- streaks ----------

async def logging_streak(conn, user_id: int, today: date) -> int:
    rows = await db.fetch_all(
        conn,
        "SELECT DISTINCT day FROM food_log WHERE user_id = ? AND day <= ? ORDER BY day DESC LIMIT 400",
        user_id,
        today.isoformat(),
    )
    days = {r["day"] for r in rows}
    # A streak survives until the end of today even if today has no logs yet.
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ---------- quests ----------

def quests_for_day(day: str) -> list[tuple[str, str, str]]:
    """Three deterministic quests per day, different each day."""
    seed = int(hashlib.sha256(day.encode()).hexdigest(), 16)
    pool = list(QUESTS)
    picked = []
    for _ in range(3):
        picked.append(pool.pop(seed % len(pool)))
        seed //= 7
    return picked


def _quest_done(code: str, entries: list[dict], totals: dict, targets: dict | None, cooked: bool) -> bool:
    if code == "log_breakfast":
        return any(e["meal"] == "breakfast" for e in entries)
    if code == "protein_meal_30":
        per_meal: dict[str, float] = {}
        for e in entries:
            per_meal[e["meal"]] = per_meal.get(e["meal"], 0) + e["protein"]
        return any(v >= 30 for v in per_meal.values())
    if code == "log_5":
        return len(entries) >= 5
    if code == "veg_or_fruit":
        return any(any(w in e["name"].lower() for w in VEG_WORDS) for e in entries)
    if code == "cook_recipe":
        return cooked
    if not targets:
        return False
    if code == "fiber_goal":
        return totals["fiber"] >= targets["fiber"]
    if code == "protein_goal":
        return totals["protein"] >= targets["protein"]
    if code == "under_kcal":
        return len(entries) >= 3 and totals["kcal"] <= targets["kcal"]
    return False


# ---------- daily evaluation ----------

async def evaluate_day(conn, user_id: int, day: str, targets: dict | None) -> list[str]:
    """Award everything earned for `day`. Returns human-readable messages for new awards."""
    news: list[str] = []
    entries = await db.fetch_all(conn, "SELECT * FROM food_log WHERE user_id = ? AND day = ?", user_id, day)
    totals = day_totals(entries)

    async def give(key: str, points: int, label: str):
        if await award(conn, user_id, key, day, points, label):
            news.append(f"+{points} XP · {label}")

    async def badge(code: str):
        if await grant_badge(conn, user_id, code):
            name, _, icon = BADGES[code]
            news.append(f"{icon} Badge unlocked: {name}")

    # Logging XP, capped per day (counted from the ledger so delete/re-add can't farm XP)
    already = await db.fetch_one(
        conn, "SELECT COUNT(*) AS n FROM xp_events WHERE user_id = ? AND day = ? AND key LIKE 'log:%'", user_id, day
    )
    slots = XP["log_food_daily_cap"] // XP["log_food"] - already["n"]
    for e in sorted(entries, key=lambda e: e["id"]):
        if slots <= 0:
            break
        if await award(conn, user_id, f"log:{e['id']}", day, XP["log_food"], "Logged food"):
            news.append(f"+{XP['log_food']} XP · Logged food")
            slots -= 1
    if entries:
        await badge("first_bite")

    cooked = bool(
        await db.fetch_one(
            conn, "SELECT 1 FROM xp_events WHERE user_id = ? AND day = ? AND key LIKE 'cook:%'", user_id, day
        )
    )

    if targets and entries:
        hit_protein = totals["protein"] >= targets["protein"]
        kcal_ok = abs(totals["kcal"] - targets["kcal"]) <= targets["kcal"] * 0.10
        carbs_ok = abs(totals["carbs"] - targets["carbs"]) <= targets["carbs"] * 0.15
        fat_ok = abs(totals["fat"] - targets["fat"]) <= targets["fat"] * 0.15
        if hit_protein:
            await give(f"protein_goal:{day}", XP["protein_goal"], "Protein goal reached")
        if kcal_ok:
            await give(f"calorie_goal:{day}", XP["calorie_goal"], "Calories on target")
            await badge("on_target")
        if hit_protein and kcal_ok and carbs_ok and fat_ok:
            await give(f"balanced:{day}", XP["balanced_day"], "Perfectly balanced day")
            await badge("balanced")

        protein_days = await db.fetch_one(
            conn, "SELECT COUNT(*) AS n FROM xp_events WHERE user_id = ? AND key LIKE 'protein_goal:%'", user_id
        )
        if protein_days["n"] >= 7:
            await badge("protein_pro")

    for code, title, _ in quests_for_day(day):
        if _quest_done(code, entries, totals, targets, cooked):
            await give(f"quest:{code}:{day}", XP["quest"], f"Quest complete: {title}")

    streak = await logging_streak(conn, user_id, date.fromisoformat(day))
    for n in (3, 7, 30):
        if streak >= n:
            await badge(f"streak_{n}")

    return news


async def summary(conn, user_id: int, day: str, targets: dict | None) -> dict:
    xp = await total_xp(conn, user_id)
    entries = await db.fetch_all(conn, "SELECT * FROM food_log WHERE user_id = ? AND day = ?", user_id, day)
    totals = day_totals(entries)
    cooked = bool(
        await db.fetch_one(
            conn, "SELECT 1 FROM xp_events WHERE user_id = ? AND day = ? AND key LIKE 'cook:%'", user_id, day
        )
    )
    earned = {r["code"]: r["earned_at"] for r in await db.fetch_all(
        conn, "SELECT code, earned_at FROM badges WHERE user_id = ?", user_id
    )}
    recent = await db.fetch_all(
        conn,
        "SELECT points, label, day FROM xp_events WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        user_id,
    )
    today_xp = await db.fetch_one(
        conn, "SELECT COALESCE(SUM(points),0) AS xp FROM xp_events WHERE user_id = ? AND day = ?", user_id, day
    )
    return {
        **level_info(xp),
        "today_xp": today_xp["xp"],
        "streak": await logging_streak(conn, user_id, date.fromisoformat(day)),
        "quests": [
            {
                "code": code,
                "title": title,
                "description": desc,
                "xp": XP["quest"],
                "done": _quest_done(code, entries, totals, targets, cooked),
            }
            for code, title, desc in quests_for_day(day)
        ],
        "badges": [
            {"code": c, "name": n, "description": d, "icon": i, "earned_at": earned.get(c)}
            for c, (n, d, i) in BADGES.items()
        ],
        "recent": recent,
    }


# ---------- helpers for routes in other domains ----------

async def give(conn, user_id: int, key: str, day: str, points: int, label: str) -> list[str]:
    """Award XP once; returns a toast message list (empty if already awarded)."""
    return [f"+{points} XP · {label}"] if await award(conn, user_id, key, day, points, label) else []


async def unlock(conn, user_id: int, code: str) -> list[str]:
    if await grant_badge(conn, user_id, code):
        name, _, icon = BADGES[code]
        return [f"{icon} Badge unlocked: {name}"]
    return []


async def after_log_change(conn, user_id: int, day: str) -> list[str]:
    return await evaluate_day(conn, user_id, day, await load_targets(conn, user_id))


async def count_events(conn, user_id: int, key_pattern: str) -> int:
    row = await db.fetch_one(
        conn, "SELECT COUNT(*) AS n FROM xp_events WHERE user_id = ? AND key LIKE ?", user_id, key_pattern
    )
    return row["n"]
