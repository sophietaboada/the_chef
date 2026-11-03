"""SQLite storage. Every user-owned table cascades on user delete, so account deletion is complete."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

-- External sign-ins (e.g. Google). Users created this way have an empty password_hash.
CREATE TABLE IF NOT EXISTS user_identities (
    provider   TEXT NOT NULL,                -- google
    subject    TEXT NOT NULL,                -- the provider's stable account id
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email      TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (provider, subject)
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id      INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    first_name   TEXT,                       -- what the app calls you
    sex          TEXT NOT NULL,              -- female | male | other
    birth_year   INTEGER NOT NULL,
    height_cm    REAL NOT NULL,
    weight_kg    REAL NOT NULL,
    job_activity TEXT NOT NULL,              -- sitting | standing | moving | physical
    goal         TEXT NOT NULL,              -- lose | maintain | gain
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sports (
    id                  INTEGER PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    sessions_per_week   REAL NOT NULL,
    minutes_per_session REAL NOT NULL,
    intensity           TEXT NOT NULL        -- light | moderate | vigorous
);

CREATE TABLE IF NOT EXISTS weight_log (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    weight_kg REAL NOT NULL,
    UNIQUE (user_id, day)
);

-- Foods are stored per 100 g so any portion can be computed.
CREATE TABLE IF NOT EXISTS foods (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,  -- never reuse ids: XP keys reference them
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    brand      TEXT,
    barcode    TEXT,
    source     TEXT NOT NULL,                -- manual | barcode | label_photo | ai_estimate
    kcal       REAL NOT NULL,
    protein    REAL NOT NULL,
    carbs      REAL NOT NULL,
    fat        REAL NOT NULL,
    fiber      REAL,
    sugar      REAL,
    serving_g  REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS foods_user ON foods(user_id, name);

CREATE TABLE IF NOT EXISTS food_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,  -- never reuse ids: XP keys reference them
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    meal       TEXT NOT NULL,                -- breakfast | lunch | dinner | snack
    food_id    INTEGER REFERENCES foods(id) ON DELETE SET NULL,
    name       TEXT NOT NULL,
    grams      REAL NOT NULL,
    kcal       REAL NOT NULL,
    protein    REAL NOT NULL,
    carbs      REAL NOT NULL,
    fat        REAL NOT NULL,
    fiber      REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS food_log_day ON food_log(user_id, day);

-- Recipes saved from AI suggestions or online sources. Lists are stored as JSON text.
CREATE TABLE IF NOT EXISTS saved_recipes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source           TEXT NOT NULL,          -- ai | spoonacular | mealdb
    external_id      TEXT NOT NULL,
    title            TEXT NOT NULL,
    minutes          INTEGER,
    servings         REAL NOT NULL DEFAULT 1,
    tags             TEXT NOT NULL DEFAULT '[]',
    ingredients      TEXT NOT NULL,
    steps            TEXT NOT NULL,
    kcal             REAL NOT NULL,          -- per serving
    protein          REAL NOT NULL,
    carbs            REAL NOT NULL,
    fat              REAL NOT NULL,
    macros_estimated INTEGER NOT NULL DEFAULT 0,
    image_url        TEXT,
    source_url       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, source, external_id)
);

-- XP ledger. `key` makes each award idempotent (e.g. 'protein_goal:2026-11-01').
CREATE TABLE IF NOT EXISTS xp_events (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key        TEXT NOT NULL,
    day        TEXT NOT NULL,
    points     INTEGER NOT NULL,
    label      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, key)
);

CREATE TABLE IF NOT EXISTS badges (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code      TEXT NOT NULL,
    earned_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, code)
);
"""


# Columns added after a table was first created. CREATE TABLE IF NOT EXISTS won't add them to
# existing databases, so connect() adds any that are missing.
ADDED_COLUMNS = [
    ("profiles", "first_name", "TEXT"),
]


async def _add_missing_columns(conn: aiosqlite.Connection) -> None:
    for table, column, decl in ADDED_COLUMNS:
        async with conn.execute(f"PRAGMA table_info({table})") as cur:
            existing = {row[1] for row in await cur.fetchall()}
        if column not in existing:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


async def connect(path: str) -> aiosqlite.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await _add_missing_columns(conn)
    await conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        await conn.execute("PRAGMA journal_mode = WAL")
    await conn.commit()
    return conn


def _params(params: tuple):
    """Allow both positional (`?`) params and a single dict of named (`:name`) params."""
    return params[0] if len(params) == 1 and isinstance(params[0], dict) else params


async def fetch_one(db: aiosqlite.Connection, sql: str, *params) -> dict | None:
    async with db.execute(sql, _params(params)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def fetch_all(db: aiosqlite.Connection, sql: str, *params) -> list[dict]:
    async with db.execute(sql, _params(params)) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def execute(db: aiosqlite.Connection, sql: str, *params) -> int:
    """Run a write and commit. Returns lastrowid."""
    async with db.execute(sql, _params(params)) as cur:
        rowid = cur.lastrowid
    await db.commit()
    return rowid
