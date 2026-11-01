"""Game balance: titles, badges, XP values and quest definitions. Tune the game here."""

LEVEL_TITLES = [
    "Kitchen Rookie",
    "Prep Cook",
    "Line Cook",
    "Station Chef",
    "Sous Chef",
    "Chef de Cuisine",
    "Head Chef",
    "Executive Chef",
    "Master Chef",
    "Legendary Chef",
]

BADGES = {
    "first_bite": ("First Bite", "Log your first food", "🍽️"),
    "scanner": ("Scanner", "Add a food by barcode", "📷"),
    "label_reader": ("Label Reader", "Read a nutrition label from a photo", "🔎"),
    "food_detective": ("Food Detective", "Estimate a food with AI", "🕵️"),
    "protein_pro": ("Protein Pro", "Hit your protein goal 7 days", "💪"),
    "on_target": ("On Target", "Finish a day within 10% of your calorie goal", "🎯"),
    "balanced": ("Perfectly Balanced", "Hit calories, protein, carbs and fat in one day", "⚖️"),
    "streak_3": ("Warming Up", "3-day logging streak", "🔥"),
    "streak_7": ("On Fire", "7-day logging streak", "🔥"),
    "streak_30": ("Unstoppable", "30-day logging streak", "🌋"),
    "weigh_in_10": ("Steady Scale", "Log your weight 10 times", "⚖️"),
    "home_cook": ("Home Cook", "Cook 5 recipes", "👩‍🍳"),
    "pantry_raider": ("Pantry Raider", "Find a recipe from your own ingredients", "🧺"),
    "collector": ("Recipe Collector", "Save 5 recipes to your book", "📚"),
    "explorer": ("Explorer", "Find recipes online", "🌍"),
}

XP = {
    "log_food": 5,          # per entry, capped per day
    "log_food_daily_cap": 25,
    "protein_goal": 30,
    "calorie_goal": 30,
    "balanced_day": 25,
    "weigh_in": 10,
    "new_food": 5,
    "cook_recipe": 15,
    "quest": 20,
    "profile": 50,
}

QUESTS = [
    ("log_breakfast", "Log a breakfast", "Start the day: log anything as breakfast"),
    ("protein_meal_30", "Protein punch", "Have a single meal with 30 g+ protein"),
    ("log_5", "Food diarist", "Log 5 or more items today"),
    ("fiber_goal", "Fiber fan", "Reach your fiber goal"),
    ("protein_goal", "Hit protein", "Reach your daily protein goal"),
    ("under_kcal", "Mindful eater", "Stay at or under your calorie goal (with 3+ items logged)"),
    ("veg_or_fruit", "Eat the rainbow", "Log a fruit or vegetable"),
    ("cook_recipe", "Chef mode", "Cook a recipe from TheChef"),
]

VEG_WORDS = (
    "apple banana berry berries orange pear grape kiwi mango melon tomato spinach broccoli "
    "carrot pepper cucumber lettuce salad kale zucchini courgette onion cabbage cauliflower "
    "bean peas asparagus mushroom avocado lemon lime plum peach cherry"
).split()
