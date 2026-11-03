from datetime import date

from thechef.foods.openfoodfacts import parse_product

PROFILE = {"first_name": "Sophie", "sex": "female", "birth_year": 1994, "height_cm": 168, "weight_kg": 65,
           "job_activity": "standing", "goal": "lose"}


async def test_requires_login(app):
    _, resp = await app.asgi_client.get("/api/log")
    assert resp.status == 401


async def test_rejects_non_json_writes(client):
    _, resp = await client.post("/api/log", content="meal=lunch", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status == 415


async def test_login_wrong_password(app, client):
    _, resp = await app.asgi_client.post("/api/auth/login", json={"username": "sophie", "password": "nope-nope"})
    assert resp.status == 400


async def test_full_day_flow(client):
    _, resp = await client.put("/api/profile", json=PROFILE)
    assert resp.status == 200, resp.text
    targets = resp.json["targets"]
    assert targets["protein"] == 130
    assert any("profile" in n for n in resp.json["news"])

    _, resp = await client.post("/api/sports", json={"name": "Running", "sessions_per_week": 3,
                                                    "minutes_per_session": 45, "intensity": "vigorous"})
    assert resp.status == 201

    _, resp = await client.post("/api/foods", json={"name": "Skyr", "kcal": 63, "protein": 11,
                                                   "carbs": 4, "fat": 0.2, "source": "manual"})
    assert resp.status == 201
    skyr = resp.json

    today = date.today().isoformat()
    _, resp = await client.post("/api/log", json={"food_id": skyr["id"], "grams": 250, "meal": "breakfast", "day": today})
    assert resp.status == 201
    assert resp.json["protein"] == 27.5
    assert any("Badge unlocked: First Bite" in n for n in resp.json["news"])

    _, resp = await client.post("/api/recipes/cook", json={"recipe_id": "chicken-stir-fry", "servings": 1,
                                                          "meal": "dinner", "day": today})
    assert resp.status == 201

    _, resp = await client.get(f"/api/log?day={today}")
    log = resp.json
    assert len(log["entries"]) == 2
    assert log["totals"]["protein"] == 67.5
    assert log["remaining"]["protein"] == log["targets"]["protein"] - 67.5

    _, resp = await client.get(f"/api/game?day={today}")
    game = resp.json
    assert game["xp"] >= 50 + 5 + 5 + 15
    assert game["streak"] == 1
    assert len(game["quests"]) == 3


async def test_log_xp_cannot_be_farmed(client):
    today = date.today().isoformat()
    quick = {"name": "Apple", "kcal": 80, "protein": 0, "carbs": 20, "fat": 0, "meal": "snack", "day": today}
    for _ in range(4):
        _, resp = await client.post("/api/log", json=quick)
        await client.request("DELETE", f"/api/log/{resp.json['id']}", json={})
    for _ in range(4):
        await client.post("/api/log", json=quick)
    _, resp = await client.get("/api/me/export")
    log_xp = sum(e["points"] for e in resp.json["xp_events"] if e["key"].startswith("log:"))
    assert log_xp == 25


async def test_users_cannot_see_each_other(app, client):
    await client.post("/api/foods", json={"name": "Secret", "kcal": 1, "protein": 1, "carbs": 1, "fat": 1})
    other = app.asgi_client
    _, resp = await other.post("/api/auth/signup", json={"username": "other", "password": "password123"})
    other.cookies = {"thechef_session": resp.cookies["thechef_session"]}
    _, resp = await other.get("/api/foods")
    assert resp.json == []


async def test_delete_account_removes_everything(app, client):
    await client.put("/api/profile", json=PROFILE)
    _, resp = await client.request("DELETE", "/api/me", json={"password": "correct-horse"})
    assert resp.status == 200
    _, resp = await app.asgi_client.post("/api/auth/login", json={"username": "sophie", "password": "correct-horse"})
    assert resp.status == 400


async def test_ai_endpoints_report_disabled(client):
    _, resp = await client.post("/api/foods/estimate", json={"description": "banana"})
    assert resp.status == 503


async def test_barcode_validation(client):
    _, resp = await client.get("/api/foods/barcode/abc")
    assert resp.status == 400


def test_parse_open_food_facts_product():
    data = {"status": 1, "product": {"product_name": "Oat drink", "brands": "Oatly, Foo",
            "nutriments": {"energy-kj_100g": 192, "proteins_100g": 1, "carbohydrates_100g": 6.7,
                           "fat_100g": 1.5, "sugars_100g": 4}, "serving_quantity": "250"}}
    p = parse_product("7394376616709", data)
    assert p["brand"] == "Oatly"
    assert p["kcal"] == 45.9
    assert p["serving_g"] == 250
    assert p["complete"] is True
    assert parse_product("123456", {"status": 0}) is None


async def test_profile_requires_first_name_and_me_returns_it(client):
    _, resp = await client.put("/api/profile", json={**PROFILE, "first_name": "  "})
    assert resp.status == 400
    _, resp = await client.get("/api/me")
    assert resp.json["first_name"] is None and resp.json["has_profile"] is False
    _, resp = await client.put("/api/profile", json=PROFILE)
    assert resp.status == 200
    _, resp = await client.get("/api/me")
    assert resp.json["first_name"] == "Sophie" and resp.json["has_profile"] is True


async def test_existing_database_gets_first_name_column(tmp_path):
    import aiosqlite

    from thechef.libs import db

    path = str(tmp_path / "old.db")
    async with aiosqlite.connect(path) as old:  # profiles table as it was before first_name
        await old.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                                created_at TEXT NOT NULL DEFAULT (datetime('now')));
            CREATE TABLE profiles (user_id INTEGER PRIMARY KEY, sex TEXT NOT NULL, birth_year INTEGER NOT NULL,
                height_cm REAL NOT NULL, weight_kg REAL NOT NULL, job_activity TEXT NOT NULL, goal TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')));
            INSERT INTO users (id, username, password_hash) VALUES (1, 'old', 'x');
            INSERT INTO profiles VALUES (1, 'female', 1990, 170, 60, 'sitting', 'lose', datetime('now'));
        """)
    conn = await db.connect(path)
    row = await db.fetch_one(conn, "SELECT first_name, weight_kg FROM profiles WHERE user_id = 1")
    assert row == {"first_name": None, "weight_kg": 60}
    await conn.close()
    conn = await db.connect(path)  # running it again is a no-op
    await conn.close()


async def test_index_links_versioned_assets_and_disables_stale_cache(app):
    _, resp = await app.asgi_client.get("/")
    assert resp.status == 200
    assert '/static/js/app.js?v=' in resp.text and '/static/css/app.css?v=' in resp.text
    assert resp.headers["cache-control"] == "no-cache"
    _, resp = await app.asgi_client.get("/static/js/app.js")
    assert resp.headers["cache-control"] == "no-cache"
