"""Recipe search (low-cal / high-protein ranking) and pantry matching.

Works on any list of recipes in the public format (ingredients as [{name, amount}]), so the
built-in catalog and a user's saved recipes are searched the same way.
"""

from __future__ import annotations

import re

from .catalog import RECIPES, STAPLES


def to_public(r: dict, **extra) -> dict:
    """Normalise a recipe dict: ingredients as [{name, amount}] and a protein-density score."""
    ingredients = [
        {"name": i[0], "amount": i[1]} if isinstance(i, (tuple, list)) else i for i in r["ingredients"]
    ]
    return {
        **{k: v for k, v in r.items() if k != "ingredients"},
        "ingredients": ingredients,
        "protein_per_100kcal": round(r["protein"] / r["kcal"] * 100, 1) if r.get("kcal") else 0,
        **extra,
    }


BUILT_IN = [to_public(r, source="built_in") for r in RECIPES]
_BY_ID = {r["id"]: r for r in BUILT_IN}

# Synonyms so 'chicken' matches 'chicken breast', 'yoghurt' matches 'yogurt', etc.
_ALIASES = {
    "yoghurt": "yogurt", "courgette": "zucchini", "prawns": "shrimp", "prawn": "shrimp",
    "capsicum": "bell pepper", "mince": "ground", "garbanzo": "chickpeas", "aubergine": "eggplant",
}
_STAPLES_NORM: set[str] = set()


def _norm(text: str) -> str:
    text = text.lower().strip()
    for a, b in _ALIASES.items():
        text = re.sub(rf"\b{a}\b", b, text)
    return re.sub(r"s\b", "", text)  # crude singular


_STAPLES_NORM = {_norm(s) for s in STAPLES}


def _matches(pantry_item: str, ingredient: str) -> bool:
    p, i = _norm(pantry_item), _norm(ingredient)
    return len(p) >= 3 and (p in i or i in p)


def get_built_in(recipe_id: str) -> dict | None:
    return _BY_ID.get(recipe_id)


def search(recipes: list[dict], q: str = "", max_kcal: float | None = None,
           min_protein: float | None = None, tag: str | None = None) -> list[dict]:
    q = q.lower().strip()
    out = []
    for r in recipes:
        if max_kcal is not None and r["kcal"] > max_kcal:
            continue
        if min_protein is not None and r["protein"] < min_protein:
            continue
        if tag == "saved":
            if r.get("saved_id") is None:
                continue
        elif tag and tag not in r["tags"]:
            continue
        hay = " ".join([r["title"], *r["tags"], *(i["name"] for i in r["ingredients"])]).lower()
        if q and not all(word in hay for word in q.split()):
            continue
        out.append(r)
    # Best protein density first: that's what "low calorie, high protein" means.
    return sorted(out, key=lambda r: r["protein_per_100kcal"], reverse=True)


def by_pantry(recipes: list[dict], pantry: list[str], max_missing: int = 2) -> list[dict]:
    pantry = [p for p in pantry if p.strip()]
    out = []
    for r in recipes:
        needed = [i["name"] for i in r["ingredients"] if _norm(i["name"]) not in _STAPLES_NORM]
        if not needed:
            continue
        have = [n for n in needed if any(_matches(p, n) for p in pantry)]
        missing = [n for n in needed if n not in have]
        if not have or len(missing) > max_missing:
            continue
        out.append({**r, "have": have, "missing": missing, "match": round(len(have) / len(needed), 2)})
    return sorted(out, key=lambda r: (len(r["missing"]), -(r.get("protein_per_100kcal") or 0)))
