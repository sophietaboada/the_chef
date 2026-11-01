"""Request-body validation helpers shared by every routes module."""

from __future__ import annotations

import base64
import binascii
from datetime import date

from sanic import Request
from sanic.exceptions import BadRequest


def body(request: Request) -> dict:
    data = request.json
    if not isinstance(data, dict):
        raise BadRequest("Expected a JSON object.")
    return data


def num(data: dict, key: str, lo: float, hi: float, required: bool = True) -> float | None:
    v = data.get(key)
    if v is None or v == "":
        if required:
            raise BadRequest(f"'{key}' is required.")
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise BadRequest(f"'{key}' must be a number.")
    if not lo <= v <= hi:
        raise BadRequest(f"'{key}' must be between {lo:g} and {hi:g}.")
    return v


def text(data: dict, key: str, max_len: int = 120, required: bool = True) -> str | None:
    raw = data.get(key)
    if raw is not None and not isinstance(raw, str):
        raise BadRequest(f"'{key}' must be text.")
    v = (raw or "").strip()
    if not v:
        if required:
            raise BadRequest(f"'{key}' is required.")
        return None
    return v[:max_len]


def choice(data: dict, key: str, options: set[str]) -> str:
    v = data.get(key)
    if v not in options:
        raise BadRequest(f"'{key}' must be one of: {', '.join(sorted(options))}.")
    return v


def day(value: str | None) -> str:
    """ISO day string; defaults to today. Clients send their local day."""
    if not value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise BadRequest("'day' must be YYYY-MM-DD.")


IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def image(data: dict, max_bytes: int = 5 * 1024 * 1024) -> tuple[str, str]:
    """Returns (base64_data, media_type) from {'image': ..., 'media_type': ...}."""
    media_type = data.get("media_type", "image/jpeg")
    if media_type not in IMAGE_TYPES:
        raise BadRequest("Image must be JPEG, PNG, WebP or GIF.")
    raw = data.get("image") or ""
    if raw.startswith("data:") and "," in raw[:100]:
        raw = raw.split(",", 1)[1]
    try:
        size = len(base64.b64decode(raw, validate=True))
    except (binascii.Error, ValueError):
        raise BadRequest("Image must be base64 encoded.")
    if size == 0 or size > max_bytes:
        raise BadRequest(f"Image must be under {max_bytes // (1024 * 1024)} MB.")
    return raw, media_type
