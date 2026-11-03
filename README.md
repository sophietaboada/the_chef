# TheChef 🍳

A personal nutrition coach: set your body details, sports and job type, get daily calorie and
macro goals, log what you eat (by barcode, label photo, AI description or manually), find
low-calorie / high-protein recipes, and level up while doing it.

Built with [Sanic](https://sanic.dev) + SQLite. The frontend is an installable web app (PWA):
it works in any desktop or phone browser and can be added to the iPhone home screen as an app.

## Quick start

```bash
# 1. Install uv if you don't have it: https://docs.astral.sh/uv/
uv sync                       # creates .venv and installs dependencies

# 2. Optional: enable AI features and online recipes
cp .env.example .env          # then set ANTHROPIC_API_KEY and/or SPOONACULAR_API_KEY

# 3. Run
uv run python -m thechef --dev          # http://127.0.0.1:8000
```

Create an account, fill in **Me → Body & lifestyle**, and start logging.

### On your iPhone

1. Run the server reachable from your network: `uv run python -m thechef --host 0.0.0.0`
2. **Live barcode scanning needs HTTPS** (browsers only allow the camera on secure pages).
   Easiest options:
   - a tunnel such as `cloudflared tunnel --url http://localhost:8000` or Tailscale Serve, or
   - your own certificate: `uv run python -m thechef --host 0.0.0.0 --cert cert.pem --key key.pem`
3. Open the URL in Safari → Share → **Add to Home Screen**.

Without HTTPS everything still works except the *live* scanner. "Photo of barcode", label photos
and typing the barcode work over plain HTTP too.

When served over HTTPS, set `THECHEF_SECURE_COOKIES=true`.

## Features

| Area | What it does |
|---|---|
| **Profile** | Sex, birth year, height, weight, job activity (sitting / standing / moving / physical), goal (lose / maintain / gain), sports with frequency, duration and intensity. Weight history with a trend line. |
| **Goals** | Mifflin-St Jeor BMR × job activity factor + MET-based exercise energy → daily kcal. Protein 1.6-2.0 g/kg depending on goal, fat ~27 % of kcal, carbs the remainder, fiber 14 g / 1000 kcal. |
| **Food lookup** | 1) saved foods, 2) **barcode** → [Open Food Facts](https://world.openfoodfacts.org), 3) **label photo** → Claude reads the nutrition table, 4) **describe** → Claude estimates, 5) **manual** entry, 6) **quick add** of raw macros. Lookups produce a draft you confirm before saving. |
| **Diary** | Per-meal log, calorie ring, macro bars vs. goals, browse previous days. |
| **Recipes** | Built-in low-cal / high-protein recipe book sorted by protein per 100 kcal, with filters; "what I have" pantry matching; **online search** via Spoonacular (exact macros, needs a free key) or TheMealDB (free, macros estimated by AI); AI recipe ideas that fit what's left of today's macros; **⭐ save** any AI or online recipe to your own recipe book (then it shows up in search and pantry matching); "I cooked this" logs it. |
| **Game** | XP and chef-themed levels, daily logging streak, 3 rotating daily quests, 13 badges, level-up celebration. XP is idempotent (no farming by deleting and re-adding). |
| **Privacy** | Hashed passwords (scrypt), hashed session tokens, per-user data isolation, data export (JSON), full account deletion. AI calls send only the photo or text you submit, never your profile. |

## Project layout

Code is organised **by domain**. Each domain keeps its logic in plain Python modules and
its HTTP endpoints in `routes.py`, so the logic can be reused outside the API (scripts, jobs,
a future native app backend).

```
thechef/
├── app.py              # Sanic app factory: wires blueprints, middleware, static files
├── config.py           # settings from env / .env
├── __main__.py         # `python -m thechef`
│
├── libs/               # generic building blocks, NO domain knowledge
│   ├── db.py           #   SQLite schema + query helpers
│   ├── security.py     #   password hashing, token hashing
│   ├── validation.py   #   request-body validation helpers
│   ├── cache.py        #   in-memory TTL cache (saves online API quota)
│   ├── llm.py          #   Claude wrapper for structured (Pydantic) outputs + error mapping
│   └── web.py          #   small Sanic helpers (503 error, require_llm)
│
├── accounts/           # sign-up, login, sessions, export, delete account
├── profile/            # body details, sports, weight → service.py loads targets
├── nutrition/          # pure math: BMR/TDEE/macro targets, portions (no DB, no HTTP)
├── foods/              # saved foods; openfoodfacts.py (barcode), ai.py (label/estimate)
├── diary/              # daily food log, totals, remaining macros
├── recipes/            # catalog.py (built-in data), search.py (ranking/pantry), library.py (saved book),
│                       #   online.py (Spoonacular, TheMealDB), ai.py, routes.py
├── gamification/       # rules.py (XP, badges, quests: tune here), engine.py, routes.py
│
└── static/             # PWA: index.html, css/, js/app.js, js/sw.js, manifest, icons
```

**Dependency rules**

- `libs/` never imports from a domain. Every domain can import `libs/`.
- `nutrition/` is pure: it imports nothing from the app.
- `diary` doesn't know about `gamification`. Gamification reads the diary and profile to decide
  awards; routes call `gamification.engine` after changes.
- Only `routes.py` files touch Sanic request/response objects.

## API

All endpoints are under `/api`, JSON in/out, cookie session auth. Writes must send
`Content-Type: application/json` (this doubles as CSRF protection).

```
POST   /auth/signup | /auth/login | /auth/logout
GET    /me                     DELETE /me {password}       GET /me/export
GET    /profile                PUT    /profile
POST   /sports                 DELETE /sports/<id>
GET    /weight                 POST   /weight {weight_kg, day?}
GET    /foods?q=               POST   /foods               DELETE /foods/<id>
GET    /foods/barcode/<code>   POST   /foods/label {image(base64), media_type, hint?}
POST   /foods/estimate {description}
GET    /log?day=               POST   /log                 DELETE /log/<id>
GET    /recipes?q=&max_kcal=&min_protein=&tag=
POST   /recipes/pantry {ingredients}   POST /recipes/ai {ingredients?, preferences?, use_remaining?}
GET    /recipes/online?source=spoonacular|mealdb&q=&ingredients=&max_kcal=&min_protein=
GET    /recipes/saved          POST /recipes/saved {recipe}   DELETE /recipes/saved/<id>
POST   /recipes/cook {recipe_id | recipe, servings, meal, day?}
GET    /game?day=
```

## Development

```bash
uv run pytest                 # tests
uv run python -m thechef --dev   # auto-reload
```

Configuration (`.env`): see [.env.example](.env.example). Set `THECHEF_ALLOW_SIGNUP=false` after
creating your account if the server is reachable by others.

### Sign in with Google (optional)

1. In [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials), create an
   **OAuth client ID** of type **Web application**.
2. Add the authorized redirect URI `https://<your-domain>/api/auth/google/callback`.
3. In `.env`, set `THECHEF_PUBLIC_URL=https://<your-domain>`, `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`,
   then restart. A "Continue with Google" button appears on the login screen.

Only Google's account id and email address are stored. Accounts created with Google have no password;
they confirm account deletion by typing their username.

## Deploying updates

On the server, after pushing your changes:

```bash
cd ~/apps/the_chef && bash deploy/deploy.sh
```

It pulls the latest commit, installs dependencies, runs the tests, restarts the app and checks
`/healthz`. If the tests or the health check fail, it rolls back to the previous commit.

> Nutrition targets are estimates for healthy adults, not medical advice.
