"""Online recipe sources. Only search terms and ingredient names are sent, never user data.

- Spoonacular: thousands of recipes with exact per-serving macros (needs SPOONACULAR_API_KEY).
- TheMealDB: free, no key, but no nutrition data; macros are estimated by AI (see recipes/ai.py).

Both return recipes in the app's public format (see search.to_public).
"""

from __future__ import annotations

import asyncio
import re

import httpx

from ..libs.cache import TTLCache
from .search import to_public

SPOONACULAR_SEARCH = "https://api.spoonacular.com/recipes/complexSearch"
MEALDB = "https://www.themealdb.com/api/json/v1/1"

_cache = TTLCache(ttl_seconds=6 * 3600)


class OnlineError(Exception):
    """Safe-to-show message."""


async def _get_json(http: httpx.AsyncClient, url: str, params: dict, headers: dict | None = None) -> dict:
    key = (url, tuple(sorted(params.items())))
    if (hit := _cache.get(key)) is not None:
        return hit
    try:
        resp = await http.get(url, params=params, headers=headers, timeout=15)
    except httpx.HTTPError as e:
        raise OnlineError(f"Couldn't reach the recipe service ({e.__class__.__name__}).") from e
    if resp.status_code in (401, 403):
        raise OnlineError("Recipe service rejected the API key.")
    if resp.status_code == 402:
        raise OnlineError("Daily recipe search quota used up - try again tomorrow.")
    if resp.status_code == 429:
        raise OnlineError("Too many recipe searches - wait a minute.")
    if resp.status_code >= 400:
        raise OnlineError(f"Recipe service error ({resp.status_code}).")
    data = resp.json()
    _cache.set(key, data)
    return data


# ---------- Spoonacular ----------

def _nutrient(nutrients: list[dict], name: str) -> float:
    for n in nutrients:
        if n.get("name") == name:
            return round(float(n.get("amount") or 0), 1)
    return 0.0


def parse_spoonacular(item: dict) -> dict:
    nutrition = item.get("nutrition") or {}
    nutrients = nutrition.get("nutrients") or []
    if item.get("extendedIngredients"):
        ingredients = [
            {"name": i.get("nameClean") or i.get("name") or "", "amount": (i.get("original") or "").strip()}
            for i in item["extendedIngredients"]
        ]
    else:
        ingredients = [
            {"name": i.get("name", ""), "amount": f"{i.get('amount', '')} {i.get('unit', '')}".strip()}
            for i in nutrition.get("ingredients") or []
        ]
    steps = [s["step"] for block in item.get("analyzedInstructions") or [] for s in block.get("steps", [])]
    tags = sorted({*(item.get("dishTypes") or []), *(item.get("diets") or [])})
    return to_public({
        "id": f"spoonacular:{item['id']}",
        "external_id": str(item["id"]),
        "source": "spoonacular",
        "title": item.get("title", "Recipe"),
        "minutes": item.get("readyInMinutes"),
        "servings": item.get("servings") or 1,
        "tags": tags,
        "ingredients": [i for i in ingredients if i["name"]],
        "steps": steps,
        "kcal": _nutrient(nutrients, "Calories"),
        "protein": _nutrient(nutrients, "Protein"),
        "carbs": _nutrient(nutrients, "Carbohydrates"),
        "fat": _nutrient(nutrients, "Fat"),
        "macros_estimated": False,
        "image_url": item.get("image"),
        "source_url": item.get("sourceUrl"),
    })


async def spoonacular_search(http: httpx.AsyncClient, api_key: str, *, query: str = "",
                             ingredients: list[str] | None = None, max_kcal: float | None = None,
                             min_protein: float | None = None, number: int = 10) -> list[dict]:
    params: dict = {
        "number": number,
        "addRecipeInformation": "true",
        "addRecipeNutrition": "true",
        "addRecipeInstructions": "true",
        "instructionsRequired": "true",
    }
    if query:
        params["query"] = query
    if ingredients:
        params["includeIngredients"] = ",".join(ingredients)
        params["sort"] = "max-used-ingredients"
    if max_kcal is not None:
        params["maxCalories"] = int(max_kcal)
    if min_protein is not None:
        params["minProtein"] = int(min_protein)
    # Key goes in a header (not the URL) so it never ends up in access logs.
    data = await _get_json(http, SPOONACULAR_SEARCH, params, headers={"x-api-key": api_key})
    return [parse_spoonacular(r) for r in data.get("results", [])]


# ---------- TheMealDB ----------

def _split_steps(instructions: str) -> list[str]:
    lines = [l.strip() for l in re.split(r"\r?\n+", instructions or "") if l.strip()]
    lines = [re.sub(r"^(step\s*)?\d+[.):]?\s*", "", l, flags=re.I) for l in lines]
    return [l for l in lines if len(l) > 3 and not re.fullmatch(r"step\s*\d*", l, re.I)]


def parse_mealdb(meal: dict) -> dict:
    ingredients = []
    for n in range(1, 21):
        name = (meal.get(f"strIngredient{n}") or "").strip()
        if name:
            ingredients.append({"name": name.lower(), "amount": (meal.get(f"strMeasure{n}") or "").strip()})
    tags = [t.strip().lower() for t in (meal.get("strTags") or "").split(",") if t.strip()]
    tags += [x.lower() for x in (meal.get("strCategory"), meal.get("strArea")) if x]
    return {
        "id": f"mealdb:{meal['idMeal']}",
        "external_id": str(meal["idMeal"]),
        "source": "mealdb",
        "title": meal.get("strMeal", "Recipe"),
        "minutes": None,
        "servings": None,
        "tags": sorted(set(tags)),
        "ingredients": ingredients,
        "steps": _split_steps(meal.get("strInstructions", "")),
        "kcal": None, "protein": None, "carbs": None, "fat": None,  # filled by AI estimate
        "macros_estimated": True,
        "image_url": meal.get("strMealThumb"),
        "source_url": meal.get("strSource") or meal.get("strYoutube") or None,
    }


def _meals(data: dict) -> list[dict]:
    """TheMealDB returns {"meals": null} or even {"meals": "no data found"} when nothing matches."""
    meals = data.get("meals")
    return meals if isinstance(meals, list) else []


async def mealdb_search(http: httpx.AsyncClient, *, query: str = "", ingredients: list[str] | None = None,
                        limit: int = 8) -> list[dict]:
    if ingredients:
        # The free API filters by one ingredient at a time; rank meals by how many of yours they use.
        lists = await asyncio.gather(*(
            _get_json(http, f"{MEALDB}/filter.php", {"i": i.strip().lower().replace(" ", "_")})
            for i in ingredients[:4]
        ))
        hits: dict[str, int] = {}
        for data in lists:
            for m in _meals(data):
                hits[m["idMeal"]] = hits.get(m["idMeal"], 0) + 1
        ids = sorted(hits, key=hits.get, reverse=True)[:limit]
        details = await asyncio.gather(*(_get_json(http, f"{MEALDB}/lookup.php", {"i": i}) for i in ids))
        meals = [m for d in details for m in _meals(d)]
    else:
        data = await _get_json(http, f"{MEALDB}/search.php", {"s": query or "chicken"})
        meals = _meals(data)[:limit]
    return [parse_mealdb(m) for m in meals]
