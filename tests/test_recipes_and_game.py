from thechef.gamification.engine import level_for_xp, quests_for_day, xp_for_level
from thechef.recipes.search import BUILT_IN, by_pantry, search


def test_search_ranks_by_protein_density():
    results = search(BUILT_IN)
    dens = [r["protein_per_100kcal"] for r in results]
    assert dens == sorted(dens, reverse=True)
    assert all(r["kcal"] <= 300 for r in search(BUILT_IN, max_kcal=300))
    assert all("vegan" in r["tags"] for r in search(BUILT_IN, tag="vegan"))
    assert any("Chicken" in r["title"] for r in search(BUILT_IN, "chicken"))


def test_pantry_matching():
    res = by_pantry(BUILT_IN, ["chicken", "broccoli", "bell pepper", "onion", "garlic", "ginger"])
    assert res[0]["id"] == "chicken-stir-fry"
    assert res[0]["missing"] == []
    assert by_pantry(BUILT_IN, ["xx"]) == []


def test_levels():
    for lvl in range(1, 15):
        assert level_for_xp(xp_for_level(lvl)) == lvl
        assert level_for_xp(xp_for_level(lvl + 1) - 1) == lvl


def test_daily_quests_deterministic_and_distinct():
    q = quests_for_day("2026-11-01")
    assert q == quests_for_day("2026-11-01")
    assert len({c for c, *_ in q}) == 3
