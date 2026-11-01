from datetime import date

import pytest

from thechef.recipes import online

SPOON_ITEM = {
    "id": 715538, "title": "Chicken Quinoa Bowl", "readyInMinutes": 25, "servings": 2,
    "image": "https://img.spoonacular.com/recipes/715538.jpg", "sourceUrl": "https://example.com/r",
    "dishTypes": ["lunch"], "diets": ["gluten free"],
    "nutrition": {"nutrients": [
        {"name": "Calories", "amount": 420.5, "unit": "kcal"}, {"name": "Protein", "amount": 38.2, "unit": "g"},
        {"name": "Carbohydrates", "amount": 35, "unit": "g"}, {"name": "Fat", "amount": 12.1, "unit": "g"}]},
    "extendedIngredients": [{"nameClean": "chicken breast", "original": "300 g chicken breast"},
                            {"name": "quinoa", "original": "1 cup quinoa"}],
    "analyzedInstructions": [{"steps": [{"number": 1, "step": "Cook quinoa."}, {"number": 2, "step": "Grill chicken."}]}],
}

MEAL = {
    "idMeal": "52795", "strMeal": "Chicken Handi", "strCategory": "Chicken", "strArea": "Indian",
    "strTags": "Curry,Spicy", "strInstructions": "STEP 1\r\nHeat oil.\r\n2. Add chicken.\r\n",
    "strMealThumb": "https://www.themealdb.com/images/x.jpg",
    "strIngredient1": "Chicken", "strMeasure1": "1.2 kg", "strIngredient2": "Onion", "strMeasure2": "5",
    "strIngredient3": "", "strMeasure3": " ",
}


def test_parse_spoonacular():
    r = online.parse_spoonacular(SPOON_ITEM)
    assert (r["kcal"], r["protein"], r["carbs"], r["fat"]) == (420.5, 38.2, 35.0, 12.1)
    assert r["ingredients"][0] == {"name": "chicken breast", "amount": "300 g chicken breast"}
    assert r["steps"] == ["Cook quinoa.", "Grill chicken."]
    assert r["protein_per_100kcal"] == 9.1
    assert r["source"] == "spoonacular" and r["external_id"] == "715538"


def test_parse_mealdb():
    r = online.parse_mealdb(MEAL)
    assert r["ingredients"] == [{"name": "chicken", "amount": "1.2 kg"}, {"name": "onion", "amount": "5"}]
    assert r["steps"] == ["Heat oil.", "Add chicken."]
    assert {"curry", "spicy", "chicken", "indian"} <= set(r["tags"])
    assert r["kcal"] is None and r["macros_estimated"] is True


@pytest.fixture
def fake_mealdb(monkeypatch):
    calls = []

    async def fake_get_json(http, url, params, headers=None):
        calls.append((url, params))
        return {"meals": [MEAL]}

    monkeypatch.setattr(online, "_get_json", fake_get_json)
    return calls


async def test_mealdb_without_ai_returns_unknown_macros(client, fake_mealdb):
    _, resp = await client.get("/api/recipes/online?source=mealdb&q=chicken")
    assert resp.status == 200, resp.text
    assert resp.json["recipes"][0]["title"] == "Chicken Handi"
    assert resp.json["recipes"][0]["kcal"] is None
    assert "enable AI" in resp.json["note"]


async def test_spoonacular_disabled_without_key(client):
    _, resp = await client.get("/api/recipes/online?source=spoonacular&q=chicken")
    assert resp.status == 503


async def test_spoonacular_search_uses_header_key(app, client, monkeypatch):
    seen = {}

    async def fake_get_json(http, url, params, headers=None):
        seen.update(url=url, params=params, headers=headers)
        return {"results": [SPOON_ITEM]}

    monkeypatch.setattr(online, "_get_json", fake_get_json)
    app.ctx.settings = type(app.ctx.settings)(**{**app.ctx.settings.__dict__, "spoonacular_key": "k123"})
    _, resp = await client.get("/api/recipes/online?source=spoonacular&q=bowl&min_protein=30&ingredients=chicken,rice")
    assert resp.status == 200, resp.text
    assert seen["headers"] == {"x-api-key": "k123"}
    assert "k123" not in str(seen["params"])
    assert seen["params"]["minProtein"] == 30
    r = resp.json["recipes"][0]
    assert r["have"] == ["chicken breast"]


async def test_save_search_and_cook_saved_recipe(client):
    recipe = online.parse_spoonacular(SPOON_ITEM)
    _, resp = await client.post("/api/recipes/saved", json={"recipe": recipe})
    assert resp.status == 201, resp.text
    saved = resp.json
    assert saved["id"].startswith("u") and saved["title"] == "Chicken Quinoa Bowl"

    _, again = await client.post("/api/recipes/saved", json={"recipe": recipe})
    assert again.status == 200 and again.json["created"] is False

    _, resp = await client.get("/api/recipes?q=quinoa")
    assert [r["title"] for r in resp.json] == ["Chicken Quinoa Bowl"]
    _, resp = await client.get("/api/recipes?tag=saved")
    assert len(resp.json) == 1

    _, resp = await client.post("/api/recipes/pantry", json={"ingredients": "quinoa, chicken"})
    assert any(r["title"] == "Chicken Quinoa Bowl" for r in resp.json["recipes"])

    today = date.today().isoformat()
    _, resp = await client.post("/api/recipes/cook", json={"recipe_id": saved["id"], "servings": 1, "meal": "lunch", "day": today})
    assert resp.status == 201, resp.text
    _, log = await client.get(f"/api/log?day={today}")
    assert log.json["totals"]["protein"] == 38.2

    _, resp = await client.request("DELETE", f"/api/recipes/saved/{saved['saved_id']}", json={})
    _, resp = await client.get("/api/recipes/saved")
    assert resp.json == []


async def test_save_rejects_unsafe_urls_and_builtin_source(client):
    recipe = {**online.parse_spoonacular(SPOON_ITEM), "source_url": "javascript:alert(1)"}
    _, resp = await client.post("/api/recipes/saved", json={"recipe": recipe})
    assert resp.json["source_url"] is None
    _, resp = await client.post("/api/recipes/saved", json={"recipe": {**recipe, "source": "built_in"}})
    assert resp.status == 400


async def test_mealdb_by_ingredients_annotates_have_missing(client, fake_mealdb):
    _, resp = await client.get("/api/recipes/online?source=mealdb&ingredients=chicken,garlic")
    assert resp.status == 200, resp.text
    r = resp.json["recipes"][0]
    assert r["have"] == ["chicken"] and r["missing"] == ["onion"]


async def test_mealdb_no_results(client, monkeypatch):
    async def fake_get_json(http, url, params, headers=None):
        return {"meals": "no data found"}

    monkeypatch.setattr(online, "_get_json", fake_get_json)
    _, resp = await client.get("/api/recipes/online?source=mealdb&ingredients=unobtainium")
    assert resp.status == 200 and resp.json["recipes"] == []
