"""Small Sanic helpers shared by routes modules."""

from __future__ import annotations

from sanic import Request
from sanic.exceptions import SanicException

from .llm import StructuredLLM


class ServiceUnavailable(SanicException):
    status_code = 503


def require_llm(request: Request) -> StructuredLLM:
    llm = request.app.ctx.llm
    if llm is None:
        raise ServiceUnavailable("AI features are off. Set ANTHROPIC_API_KEY to enable them.")
    return llm
