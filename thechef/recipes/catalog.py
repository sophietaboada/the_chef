"""Built-in recipe book (works offline). Macros are per serving and approximate.

Add recipes here; each needs id, title, minutes, servings, tags, kcal/protein/carbs/fat,
ingredients as (name, amount) pairs, and steps.
"""

from __future__ import annotations

# Ingredients everyone is assumed to have; they don't count against a pantry match.
STAPLES = {
    "salt", "pepper", "black pepper", "water", "olive oil", "oil", "cooking spray", "garlic powder",
    "paprika", "chili flakes", "cumin", "oregano", "cinnamon", "vinegar", "soy sauce", "mustard",
    "dried herbs", "italian herbs", "curry powder", "baking powder", "vanilla",
}

RECIPES: list[dict] = [
    {
        "id": "greek-yogurt-bowl",
        "title": "Protein Greek Yogurt Bowl",
        "minutes": 5, "servings": 1, "tags": ["breakfast", "no-cook", "vegetarian"],
        "kcal": 330, "protein": 32, "carbs": 35, "fat": 7,
        "ingredients": [
            ("greek yogurt", "250 g, 0-2% fat"), ("berries", "100 g"), ("oats", "20 g"),
            ("honey", "1 tsp"), ("cinnamon", "pinch"),
        ],
        "steps": ["Spoon yogurt into a bowl.", "Top with berries, oats and a drizzle of honey.", "Dust with cinnamon."],
    },
    {
        "id": "egg-white-veggie-omelette",
        "title": "Egg White Veggie Omelette",
        "minutes": 12, "servings": 1, "tags": ["breakfast", "vegetarian", "low-carb"],
        "kcal": 240, "protein": 30, "carbs": 9, "fat": 9,
        "ingredients": [
            ("egg whites", "200 ml"), ("eggs", "1"), ("spinach", "1 handful"), ("tomato", "1"),
            ("feta", "20 g"), ("salt", ""), ("pepper", ""), ("cooking spray", ""),
        ],
        "steps": [
            "Whisk egg whites with the whole egg, salt and pepper.",
            "Wilt spinach and diced tomato in a sprayed non-stick pan.",
            "Pour in the eggs, cook on medium-low until set, crumble feta on top and fold.",
        ],
    },
    {
        "id": "overnight-protein-oats",
        "title": "Overnight Protein Oats",
        "minutes": 5, "servings": 1, "tags": ["breakfast", "meal-prep", "vegetarian"],
        "kcal": 390, "protein": 35, "carbs": 45, "fat": 8,
        "ingredients": [
            ("oats", "40 g"), ("protein powder", "1 scoop (30 g)"), ("skyr", "100 g"),
            ("milk", "120 ml skimmed or plant"), ("banana", "1/2"), ("cinnamon", "pinch"),
        ],
        "steps": ["Mix everything except the banana in a jar.", "Refrigerate overnight.", "Top with sliced banana."],
    },
    {
        "id": "cottage-cheese-pancakes",
        "title": "Cottage Cheese Pancakes",
        "minutes": 15, "servings": 2, "tags": ["breakfast", "vegetarian"],
        "kcal": 280, "protein": 24, "carbs": 25, "fat": 9,
        "ingredients": [
            ("cottage cheese", "200 g"), ("eggs", "2"), ("oats", "50 g"), ("baking powder", "1 tsp"),
            ("berries", "to serve"),
        ],
        "steps": [
            "Blend cottage cheese, eggs, oats and baking powder until smooth.",
            "Cook small pancakes in a non-stick pan, 2 min per side.",
            "Serve with berries.",
        ],
    },
    {
        "id": "chicken-stir-fry",
        "title": "15-Minute Chicken Stir-Fry",
        "minutes": 15, "servings": 2, "tags": ["dinner", "lunch", "dairy-free"],
        "kcal": 340, "protein": 40, "carbs": 18, "fat": 11,
        "ingredients": [
            ("chicken breast", "300 g"), ("broccoli", "200 g"), ("bell pepper", "1"), ("onion", "1"),
            ("garlic", "2 cloves"), ("ginger", "1 tsp grated"), ("soy sauce", "2 tbsp"), ("oil", "1 tbsp"),
        ],
        "steps": [
            "Slice chicken thinly and stir-fry in hot oil for 5 min.",
            "Add sliced vegetables, garlic and ginger; fry 4-5 min.",
            "Add soy sauce and a splash of water, toss and serve (with rice if it fits your carbs).",
        ],
    },
    {
        "id": "tuna-salad-wraps",
        "title": "Tuna Lettuce Wraps",
        "minutes": 10, "servings": 2, "tags": ["lunch", "no-cook", "low-carb"],
        "kcal": 220, "protein": 30, "carbs": 6, "fat": 8,
        "ingredients": [
            ("canned tuna", "2 cans (in water)"), ("greek yogurt", "60 g"), ("mustard", "1 tsp"),
            ("cucumber", "1/2"), ("red onion", "1/4"), ("lettuce", "8 leaves"), ("lemon", "1/2"),
        ],
        "steps": [
            "Drain tuna; mix with yogurt, mustard, lemon juice and finely diced cucumber and onion.",
            "Spoon into lettuce leaves and wrap.",
        ],
    },
    {
        "id": "turkey-chili",
        "title": "Lean Turkey Chili",
        "minutes": 35, "servings": 4, "tags": ["dinner", "meal-prep", "dairy-free"],
        "kcal": 360, "protein": 36, "carbs": 30, "fat": 10,
        "ingredients": [
            ("ground turkey", "500 g lean"), ("kidney beans", "1 can"), ("canned tomatoes", "1 can"),
            ("onion", "1"), ("bell pepper", "1"), ("garlic", "2 cloves"), ("cumin", "1 tsp"),
            ("paprika", "1 tsp"), ("chili flakes", "to taste"), ("oil", "1 tsp"),
        ],
        "steps": [
            "Brown turkey in a pot with a little oil.",
            "Add chopped onion, pepper, garlic and spices; cook 3 min.",
            "Add tomatoes and drained beans, simmer 20 min.",
        ],
    },
    {
        "id": "salmon-traybake",
        "title": "Salmon & Veg Traybake",
        "minutes": 25, "servings": 2, "tags": ["dinner", "dairy-free", "low-carb"],
        "kcal": 420, "protein": 34, "carbs": 14, "fat": 25,
        "ingredients": [
            ("salmon fillet", "2 x 125 g"), ("zucchini", "1"), ("cherry tomatoes", "200 g"),
            ("red onion", "1"), ("lemon", "1"), ("olive oil", "1 tbsp"), ("italian herbs", "1 tsp"),
        ],
        "steps": [
            "Heat oven to 200°C.",
            "Toss chopped veg with oil and herbs on a tray; roast 10 min.",
            "Add salmon and lemon slices, roast 12 more minutes.",
        ],
    },
    {
        "id": "shrimp-zoodles",
        "title": "Garlic Shrimp Zoodles",
        "minutes": 15, "servings": 2, "tags": ["dinner", "low-carb", "dairy-free"],
        "kcal": 230, "protein": 30, "carbs": 10, "fat": 8,
        "ingredients": [
            ("shrimp", "300 g"), ("zucchini", "2"), ("garlic", "3 cloves"), ("cherry tomatoes", "150 g"),
            ("chili flakes", "pinch"), ("olive oil", "1 tbsp"), ("lemon", "1/2"),
        ],
        "steps": [
            "Spiralize zucchini.",
            "Sauté garlic and chili in oil, add shrimp and cook 3 min.",
            "Add tomatoes and zoodles, toss 2 min, finish with lemon.",
        ],
    },
    {
        "id": "chicken-burrito-bowl",
        "title": "Chicken Burrito Bowl",
        "minutes": 25, "servings": 2, "tags": ["lunch", "dinner", "meal-prep"],
        "kcal": 480, "protein": 42, "carbs": 50, "fat": 11,
        "ingredients": [
            ("chicken breast", "300 g"), ("rice", "100 g dry"), ("black beans", "1/2 can"),
            ("corn", "80 g"), ("tomato", "1"), ("greek yogurt", "50 g"), ("lime", "1"),
            ("cumin", "1 tsp"), ("paprika", "1 tsp"),
        ],
        "steps": [
            "Cook rice.",
            "Season chicken with cumin and paprika, pan-fry 6-7 min per side and slice.",
            "Build bowls with rice, beans, corn, diced tomato and chicken; top with yogurt and lime.",
        ],
    },
    {
        "id": "lentil-spinach-curry",
        "title": "Red Lentil & Spinach Curry",
        "minutes": 30, "servings": 3, "tags": ["dinner", "vegan", "meal-prep"],
        "kcal": 340, "protein": 20, "carbs": 50, "fat": 6,
        "ingredients": [
            ("red lentils", "200 g"), ("canned tomatoes", "1 can"), ("spinach", "150 g"), ("onion", "1"),
            ("garlic", "2 cloves"), ("ginger", "1 tsp"), ("curry powder", "2 tsp"), ("oil", "1 tsp"),
        ],
        "steps": [
            "Soften onion, garlic and ginger in oil; add curry powder.",
            "Add lentils, tomatoes and 500 ml water; simmer 20 min.",
            "Stir in spinach until wilted.",
        ],
    },
    {
        "id": "tofu-scramble",
        "title": "Smoky Tofu Scramble",
        "minutes": 12, "servings": 2, "tags": ["breakfast", "vegan", "low-carb"],
        "kcal": 220, "protein": 22, "carbs": 7, "fat": 12,
        "ingredients": [
            ("firm tofu", "300 g"), ("spinach", "1 handful"), ("bell pepper", "1/2"),
            ("paprika", "1 tsp"), ("turmeric", "1/2 tsp"), ("soy sauce", "1 tsp"), ("oil", "1 tsp"),
        ],
        "steps": ["Crumble tofu into a hot oiled pan.", "Add spices, soy sauce and veg; cook 5-6 min."],
    },
    {
        "id": "cottage-cheese-pasta",
        "title": "Creamy Cottage Cheese Pasta",
        "minutes": 15, "servings": 2, "tags": ["dinner", "vegetarian"],
        "kcal": 450, "protein": 30, "carbs": 60, "fat": 9,
        "ingredients": [
            ("pasta", "140 g dry"), ("cottage cheese", "200 g"), ("parmesan", "20 g"),
            ("garlic", "1 clove"), ("spinach", "100 g"), ("pepper", ""),
        ],
        "steps": [
            "Cook pasta; save a little pasta water.",
            "Blend cottage cheese, parmesan and garlic into a sauce.",
            "Toss pasta with spinach and sauce, loosening with pasta water.",
        ],
    },
    {
        "id": "beef-broccoli",
        "title": "Lean Beef & Broccoli",
        "minutes": 20, "servings": 2, "tags": ["dinner", "dairy-free", "low-carb"],
        "kcal": 360, "protein": 38, "carbs": 14, "fat": 16,
        "ingredients": [
            ("lean beef", "300 g steak strips"), ("broccoli", "250 g"), ("garlic", "2 cloves"),
            ("ginger", "1 tsp"), ("soy sauce", "2 tbsp"), ("honey", "1 tsp"), ("oil", "1 tbsp"),
        ],
        "steps": [
            "Sear beef strips in hot oil 2-3 min, remove.",
            "Stir-fry broccoli with garlic and ginger 4 min, add a splash of water.",
            "Return beef, add soy sauce and honey, toss to glaze.",
        ],
    },
    {
        "id": "chickpea-tuna-salad",
        "title": "Chickpea & Tuna Power Salad",
        "minutes": 10, "servings": 2, "tags": ["lunch", "no-cook", "dairy-free"],
        "kcal": 350, "protein": 32, "carbs": 30, "fat": 10,
        "ingredients": [
            ("canned tuna", "1 can"), ("chickpeas", "1 can"), ("cucumber", "1"), ("cherry tomatoes", "150 g"),
            ("red onion", "1/4"), ("lemon", "1"), ("olive oil", "1 tbsp"),
        ],
        "steps": ["Drain tuna and chickpeas.", "Chop vegetables and toss everything with lemon and oil."],
    },
    {
        "id": "protein-smoothie",
        "title": "Berry Protein Smoothie",
        "minutes": 3, "servings": 1, "tags": ["breakfast", "snack", "no-cook", "vegetarian"],
        "kcal": 280, "protein": 30, "carbs": 30, "fat": 4,
        "ingredients": [
            ("protein powder", "1 scoop"), ("berries", "150 g frozen"), ("milk", "250 ml skimmed or plant"),
            ("spinach", "1 handful"),
        ],
        "steps": ["Blend everything until smooth."],
    },
    {
        "id": "egg-muffins",
        "title": "Egg & Veggie Muffins",
        "minutes": 25, "servings": 3, "tags": ["breakfast", "snack", "meal-prep", "low-carb"],
        "kcal": 190, "protein": 17, "carbs": 4, "fat": 12,
        "ingredients": [
            ("eggs", "6"), ("egg whites", "100 ml"), ("bell pepper", "1"), ("spinach", "1 handful"),
            ("feta", "40 g"), ("salt", ""), ("pepper", ""),
        ],
        "steps": [
            "Heat oven to 180°C and grease a muffin tin.",
            "Whisk eggs and whites, stir in chopped veg and feta.",
            "Fill 6 cups and bake 18-20 min. 2 muffins per serving.",
        ],
    },
    {
        "id": "chicken-caesar-light",
        "title": "Light Chicken Caesar",
        "minutes": 20, "servings": 2, "tags": ["lunch", "low-carb"],
        "kcal": 330, "protein": 40, "carbs": 10, "fat": 14,
        "ingredients": [
            ("chicken breast", "300 g"), ("lettuce", "1 romaine head"), ("parmesan", "20 g"),
            ("greek yogurt", "60 g"), ("lemon", "1/2"), ("mustard", "1 tsp"), ("garlic", "1 clove"),
        ],
        "steps": [
            "Grill or pan-fry chicken, then slice.",
            "Whisk yogurt, lemon, mustard, grated garlic and half the parmesan into a dressing.",
            "Toss lettuce with dressing, top with chicken and remaining parmesan.",
        ],
    },
]
