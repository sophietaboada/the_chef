"""Barcode lookup via Open Food Facts (free, open database). Only the barcode is sent."""

from __future__ import annotations

import re

import httpx

API = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
FIELDS = "product_name,brands,nutriments,serving_quantity,image_front_small_url"
HEADERS = {"User-Agent": "TheChef/0.1 (personal nutrition app)"}


class LookupFailed(Exception):
    pass


def valid_barcode(code: str) -> bool:
    return bool(re.fullmatch(r"\d{6,14}", code))


def _num(nutriments: dict, *keys: str) -> float | None:
    for k in keys:
        v = nutriments.get(k)
        if v is not None and v != "":
            try:
                return round(float(v), 2)
            except (TypeError, ValueError):
                continue
    return None


def parse_product(code: str, data: dict) -> dict | None:
    if data.get("status") != 1 or "product" not in data:
        return None
    p = data["product"]
    n = p.get("nutriments", {})
    kcal = _num(n, "energy-kcal_100g")
    if kcal is None:
        kj = _num(n, "energy-kj_100g", "energy_100g")
        kcal = round(kj / 4.184, 1) if kj is not None else None
    result = {
        "name": p.get("product_name") or f"Product {code}",
        "brand": (p.get("brands") or "").split(",")[0].strip() or None,
        "barcode": code,
        "source": "barcode",
        "kcal": kcal,
        "protein": _num(n, "proteins_100g"),
        "carbs": _num(n, "carbohydrates_100g"),
        "fat": _num(n, "fat_100g"),
        "fiber": _num(n, "fiber_100g"),
        "sugar": _num(n, "sugars_100g"),
        "serving_g": _num(p, "serving_quantity"),
        "image_url": p.get("image_front_small_url"),
    }
    result["complete"] = all(result[k] is not None for k in ("kcal", "protein", "carbs", "fat"))
    return result


async def lookup(code: str, client: httpx.AsyncClient | None = None) -> dict | None:
    if not valid_barcode(code):
        raise LookupFailed("Barcodes are 6-14 digits.")
    own = client is None
    client = client or httpx.AsyncClient(timeout=10, headers=HEADERS)
    try:
        resp = await client.get(API.format(code=code), params={"fields": FIELDS})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return parse_product(code, resp.json())
    except httpx.HTTPError as e:
        raise LookupFailed(f"Open Food Facts lookup failed: {e.__class__.__name__}") from e
    finally:
        if own:
            await client.aclose()
