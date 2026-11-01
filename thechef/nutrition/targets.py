"""Energy and macro goal calculations.

BMR: Mifflin-St Jeor. Daily energy = BMR x job activity factor + averaged exercise energy.
Exercise energy uses METs, minus the resting MET already counted in BMR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

JOB_FACTORS = {
    "sitting": 1.2,    # desk job, mostly seated
    "standing": 1.35,  # retail, lab, teaching
    "moving": 1.5,     # nurse, waiter, walking a lot
    "physical": 1.7,   # construction, warehouse, manual labour
}

INTENSITY_METS = {"light": 3.5, "moderate": 6.0, "vigorous": 9.0}

GOALS = {"lose", "maintain", "gain"}
SEXES = {"female", "male", "other"}

PROTEIN_G_PER_KG = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}


@dataclass
class Targets:
    bmr: int
    tdee: int
    kcal: int
    protein: int
    carbs: int
    fat: int
    fiber: int
    exercise_kcal_per_day: int
    bmi: float

    def as_dict(self) -> dict:
        return asdict(self)


def age_from_birth_year(birth_year: int, today: date | None = None) -> int:
    today = today or date.today()
    return max(0, today.year - birth_year)


def bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    offset = {"male": 5, "female": -161}.get(sex, -78)  # 'other' uses the midpoint
    return base + offset


def exercise_kcal_per_day(sports: list[dict], weight_kg: float) -> float:
    weekly = 0.0
    for s in sports:
        met = INTENSITY_METS.get(s["intensity"], INTENSITY_METS["moderate"])
        hours = s["minutes_per_session"] / 60 * s["sessions_per_week"]
        weekly += (met - 1) * weight_kg * hours  # net of resting energy
    return weekly / 7


def compute_targets(profile: dict, sports: list[dict], today: date | None = None) -> Targets:
    weight = profile["weight_kg"]
    height = profile["height_cm"]
    age = age_from_birth_year(profile["birth_year"], today)
    goal = profile["goal"]

    b = bmr(profile["sex"], weight, height, age)
    ex = exercise_kcal_per_day(sports, weight)
    tdee = b * JOB_FACTORS.get(profile["job_activity"], 1.2) + ex

    if goal == "lose":
        kcal = tdee - min(tdee * 0.2, 600)
    elif goal == "gain":
        kcal = tdee + min(tdee * 0.1, 350)
    else:
        kcal = tdee
    floor = {"male": 1500, "female": 1200}.get(profile["sex"], 1350)
    kcal = max(kcal, floor)

    # For high BMI, base protein on the weight at BMI 27 to avoid unrealistic targets.
    bmi = weight / (height / 100) ** 2
    protein_ref_weight = min(weight, 27 * (height / 100) ** 2) if bmi > 30 else weight
    protein = PROTEIN_G_PER_KG[goal] * protein_ref_weight

    fat = kcal * 0.27 / 9
    carbs = max(0.0, (kcal - protein * 4 - fat * 9) / 4)
    fiber = kcal / 1000 * 14

    return Targets(
        bmr=round(b),
        tdee=round(tdee),
        kcal=round(kcal),
        protein=round(protein),
        carbs=round(carbs),
        fat=round(fat),
        fiber=round(fiber),
        exercise_kcal_per_day=round(ex),
        bmi=round(bmi, 1),
    )


def portion(food: dict, grams: float) -> dict:
    """Scale a per-100 g food to a portion."""
    f = grams / 100
    return {
        "kcal": round(food["kcal"] * f, 1),
        "protein": round(food["protein"] * f, 1),
        "carbs": round(food["carbs"] * f, 1),
        "fat": round(food["fat"] * f, 1),
        "fiber": round((food.get("fiber") or 0) * f, 1),
    }
