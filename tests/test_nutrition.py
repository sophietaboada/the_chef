from datetime import date

from thechef.nutrition import compute_targets, portion

PROFILE = {"sex": "female", "birth_year": 1994, "height_cm": 168, "weight_kg": 65,
           "job_activity": "sitting", "goal": "maintain"}


def test_targets_reasonable():
    t = compute_targets(PROFILE, [], today=date(2026, 11, 1))
    assert 1350 < t.bmr < 1450          # Mifflin-St Jeor for a 32 y/o, 168 cm, 65 kg woman
    assert t.tdee == round(t.bmr * 1.2)
    assert t.kcal == t.tdee
    assert t.protein == round(1.6 * 65)
    assert abs(t.protein * 4 + t.carbs * 4 + t.fat * 9 - t.kcal) < 15


def test_sports_and_job_raise_energy():
    base = compute_targets(PROFILE, [])
    active = compute_targets({**PROFILE, "job_activity": "moving"},
                             [{"intensity": "vigorous", "minutes_per_session": 60, "sessions_per_week": 4}])
    assert active.tdee > base.tdee + 500
    assert active.exercise_kcal_per_day > 250


def test_lose_has_deficit_and_floor():
    lose = compute_targets({**PROFILE, "goal": "lose"}, [])
    assert lose.kcal < compute_targets(PROFILE, []).kcal
    tiny = compute_targets({**PROFILE, "goal": "lose", "weight_kg": 40, "height_cm": 150}, [])
    assert tiny.kcal >= 1200


def test_portion():
    assert portion({"kcal": 200, "protein": 10, "carbs": 20, "fat": 5, "fiber": None}, 50) == {
        "kcal": 100.0, "protein": 5.0, "carbs": 10.0, "fat": 2.5, "fiber": 0.0}
