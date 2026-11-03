"""Sanic application factory."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from sanic import Request, Sanic, json
from sanic.response import file, html

from .accounts.google import bp as google_bp
from .accounts.routes import bp as accounts_bp
from .config import Settings
from .diary.routes import bp as diary_bp
from .foods.openfoodfacts import HEADERS as OFF_HEADERS
from .foods.routes import bp as foods_bp
from .gamification.routes import bp as gamification_bp
from .libs import db
from .libs.llm import StructuredLLM
from .profile.routes import bp as profile_bp
from .recipes.routes import bp as recipes_bp

STATIC = Path(__file__).parent / "static"
VERSIONED_ASSETS = ("/static/js/app.js", "/static/css/app.css")


def _index_html() -> str:
    """index.html with a content hash on the JS/CSS links, so browsers and Cloudflare fetch the
    new files after each deploy instead of mixing a new page with an old cached script."""
    html = (STATIC / "index.html").read_text()
    for asset in VERSIONED_ASSETS:
        digest = hashlib.sha256((STATIC / asset.removeprefix("/static/")).read_bytes()).hexdigest()[:10]
        html = html.replace(f'"{asset}"', f'"{asset}?v={digest}"')
    return html
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def create_app(settings: Settings | None = None, name: str = "TheChef") -> Sanic:
    settings = settings or Settings.from_env()
    app = Sanic(name)
    app.config.FALLBACK_ERROR_FORMAT = "json"
    app.config.REQUEST_MAX_SIZE = 8 * 1024 * 1024  # room for a 5 MB base64 photo
    app.ctx.settings = settings

    @app.before_server_start
    async def setup(app: Sanic):
        app.ctx.db = await db.connect(settings.db_path)
        app.ctx.http = httpx.AsyncClient(timeout=10, headers=OFF_HEADERS)
        app.ctx.llm = StructuredLLM(settings.model) if settings.ai_enabled else None

    @app.after_server_stop
    async def teardown(app: Sanic):
        await app.ctx.http.aclose()
        await app.ctx.db.close()

    @app.on_request
    async def require_json(request: Request):
        """CSRF guard: browsers can't send cross-site application/json without a CORS preflight,
        which this server never approves."""
        if request.method in UNSAFE_METHODS and request.path.startswith("/api/"):
            if not (request.content_type or "").startswith("application/json"):
                return json({"description": "Content-Type must be application/json", "status": 415}, status=415)

    @app.on_response
    async def security_headers(request: Request, response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        else:
            # Always revalidate the page and static files (cheap 304s) so a deploy shows up at once.
            response.headers.setdefault("Cache-Control", "no-cache")

    for bp in (accounts_bp, google_bp, profile_bp, foods_bp, diary_bp, recipes_bp, gamification_bp):
        app.blueprint(bp)

    app.static("/static", STATIC, name="static")

    index_html = _index_html()

    @app.get("/")
    async def index(_):
        return html(index_html)

    @app.get("/manifest.webmanifest")
    async def manifest(_):
        return await file(STATIC / "manifest.webmanifest", mime_type="application/manifest+json")

    @app.get("/sw.js")
    async def service_worker(_):
        # Served from the root so the worker controls the whole app.
        return await file(STATIC / "js" / "sw.js", mime_type="text/javascript")

    @app.get("/healthz")
    async def health(_):
        return json({"ok": True, "ai": settings.ai_enabled})

    return app
