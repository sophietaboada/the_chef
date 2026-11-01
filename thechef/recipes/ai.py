"""AI recipe ideas. Sends only ingredients, preferences and a calorie/protein budget."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..libs.llm import StructuredLLM


class RecipeIngredient(BaseModel):
    name: str
    amount: str


class AIRecipe(BaseModel):
    title: str
    minutes: int
    servings: int
    tags: list[str]
    ingredients: list[RecipeIngredient]
    steps: list[str]
    kcal: float = Field(description="per serving")
    protein: float = Field(description="grams per serving")
    carbs: float = Field(description="grams per serving")
    fat: float = Field(description="grams per serving")


class AIRecipes(BaseModel):
    recipes: list[AIRecipe]


PROMPT = """Suggest {count} easy, low-calorie, high-protein recipes.

Ingredients available: {ingredients}
Preferences or restrictions: {preferences}
Remaining budget for this meal (approximate): {budget}

Rules:
- Prioritise protein density (aim for 25 g+ protein per serving under 500 kcal).
- Use mostly the available ingredients; assume basic pantry staples (oil, salt, spices) exist.
- Keep it simple: under 30 minutes, few steps, home-kitchen equipment.
- Macros are per serving and must be realistic for the listed amounts."""


async def suggest(llm: StructuredLLM, ingredients: list[str], preferences: str,
                  budget: dict | None, count: int = 3) -> list[dict]:
    budget_text = f"{budget['kcal']} kcal, aim for {budget['protein']} g protein" if budget else "not specified"
    prompt = PROMPT.format(
        count=count,
        ingredients=", ".join(ingredients) if ingredients else "anything common",
        preferences=preferences or "none",
        budget=budget_text,
    )
    result = await llm.parse(prompt, AIRecipes, effort="medium")
    out = []
    for r in result.recipes:
        d = r.model_dump()
        d.update(id=None, source="ai", external_id=None,
                 protein_per_100kcal=round(d["protein"] / d["kcal"] * 100, 1) if d["kcal"] else 0)
        out.append(d)
    return out


# ---------- macro estimates for recipes without nutrition data (TheMealDB) ----------

class RecipeMacros(BaseModel):
    index: int = Field(description="The recipe's index from the input list")
    servings: int = Field(description="Realistic number of servings for the listed amounts")
    minutes: int = Field(description="Estimated total time")
    kcal: float = Field(description="per serving")
    protein: float = Field(description="grams per serving")
    carbs: float = Field(description="grams per serving")
    fat: float = Field(description="grams per serving")


class RecipeMacrosList(BaseModel):
    recipes: list[RecipeMacros]


ESTIMATE_PROMPT = """Estimate per-serving nutrition for each recipe below, using the listed ingredient
amounts and standard food composition tables. Choose a realistic serving count for the amounts.
Return one entry per recipe, using its index.

{recipes}"""


async def estimate_macros(llm: StructuredLLM, recipes: list[dict]) -> list[dict]:
    """Fills kcal/protein/carbs/fat/servings/minutes in place (one model call for the batch)."""
    if not recipes:
        return recipes
    blocks = []
    for i, r in enumerate(recipes):
        ings = "; ".join(f"{g['amount']} {g['name']}".strip() for g in r["ingredients"])
        blocks.append(f"<recipe index=\"{i}\">\n{r['title']}\nIngredients: {ings}\n</recipe>")
    result = await llm.parse(ESTIMATE_PROMPT.format(recipes="\n".join(blocks)), RecipeMacrosList, effort="low")
    for m in result.recipes:
        if 0 <= m.index < len(recipes):
            recipes[m.index].update(
                servings=m.servings, minutes=recipes[m.index].get("minutes") or m.minutes,
                kcal=round(m.kcal), protein=round(m.protein, 1), carbs=round(m.carbs, 1), fat=round(m.fat, 1),
                macros_estimated=True,
            )
    return recipes
