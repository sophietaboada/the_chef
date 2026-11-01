"""AI food lookups: read a nutrition label photo, or estimate macros from a description.
Only the image or description is sent to the model, never the user's profile.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..libs.llm import StructuredLLM


class FoodDraft(BaseModel):
    name: str
    brand: str | None = None
    kcal: float = Field(description="kcal per 100 g (or 100 ml)")
    protein: float = Field(description="grams per 100 g")
    carbs: float = Field(description="grams per 100 g")
    fat: float = Field(description="grams per 100 g")
    fiber: float | None = Field(default=None, description="grams per 100 g")
    sugar: float | None = Field(default=None, description="grams per 100 g")
    serving_g: float | None = Field(default=None, description="typical serving size in grams")
    confidence: Literal["high", "medium", "low"]
    notes: str = Field(description="One short sentence on assumptions or anything unreadable")


LABEL_PROMPT = """Read the nutrition facts label in this photo and return values per 100 g (or 100 ml).
If the label only shows per-serving values, convert using the serving weight printed on the label.
If a value is not printed, estimate it from the product type and say so in notes.
Use kcal (convert from kJ by dividing by 4.184 if only kJ is shown).
If the image isn't a nutrition label, return your best guess with confidence "low" and explain in notes.
{hint}"""

ESTIMATE_PROMPT = """Estimate the nutrition per 100 g for this food, as eaten:

<food>{description}</food>

Use typical values from standard food composition tables. If it's a composite dish, estimate the
whole dish per 100 g. Set serving_g to a typical portion. Be honest about uncertainty in confidence."""


async def read_label(llm: StructuredLLM, image_b64: str, media_type: str, hint: str = "") -> dict:
    hint_text = f"Extra context from the user: <hint>{hint}</hint>" if hint else ""
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
        {"type": "text", "text": LABEL_PROMPT.format(hint=hint_text)},
    ]
    draft = await llm.parse(content, FoodDraft, effort="low")
    return {**draft.model_dump(), "source": "label_photo"}


async def estimate(llm: StructuredLLM, description: str) -> dict:
    draft = await llm.parse(ESTIMATE_PROMPT.format(description=description), FoodDraft, effort="medium")
    return {**draft.model_dump(), "source": "ai_estimate"}
