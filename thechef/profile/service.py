"""Body details, sports and weight history, plus the daily targets derived from them."""

from __future__ import annotations

from .. import nutrition
from ..libs import db


async def load(conn, user_id: int) -> dict:
    profile = await db.fetch_one(conn, "SELECT * FROM profiles WHERE user_id = ?", user_id)
    sports = await db.fetch_all(conn, "SELECT * FROM sports WHERE user_id = ? ORDER BY id", user_id)
    targets = nutrition.compute_targets(profile, sports).as_dict() if profile else None
    return {"profile": profile, "sports": sports, "targets": targets}


async def load_targets(conn, user_id: int) -> dict | None:
    return (await load(conn, user_id))["targets"]


async def save(conn, user_id: int, values: dict) -> None:
    await db.execute(
        conn,
        """INSERT INTO profiles (user_id, sex, birth_year, height_cm, weight_kg, job_activity, goal)
           VALUES (:uid, :sex, :birth_year, :height_cm, :weight_kg, :job_activity, :goal)
           ON CONFLICT(user_id) DO UPDATE SET sex=excluded.sex, birth_year=excluded.birth_year,
             height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,
             job_activity=excluded.job_activity, goal=excluded.goal, updated_at=datetime('now')""",
        {"uid": user_id, **values},
    )


async def record_weight(conn, user_id: int, day: str, weight_kg: float) -> int:
    """Upsert a weigh-in; if it's the latest one, it becomes the profile weight. Returns weigh-in count."""
    await db.execute(
        conn,
        "INSERT INTO weight_log (user_id, day, weight_kg) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, day) DO UPDATE SET weight_kg = excluded.weight_kg",
        user_id, day, weight_kg,
    )
    latest = await db.fetch_one(
        conn, "SELECT day FROM weight_log WHERE user_id = ? ORDER BY day DESC LIMIT 1", user_id
    )
    if latest["day"] == day:
        await db.execute(conn, "UPDATE profiles SET weight_kg = ? WHERE user_id = ?", weight_kg, user_id)
    count = await db.fetch_one(conn, "SELECT COUNT(*) AS n FROM weight_log WHERE user_id = ?", user_id)
    return count["n"]
