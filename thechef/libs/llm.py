"""Thin wrapper around Claude for structured (Pydantic) outputs, with friendly errors.

Domain modules (foods/ai.py, recipes/ai.py) own their prompts and schemas; this module only
knows how to call the model and turn failures into `LLMError`.
"""

from __future__ import annotations

import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

log = logging.getLogger("thechef.llm")

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Safe-to-show message for the user."""


class StructuredLLM:
    def __init__(self, model: str, client: anthropic.AsyncAnthropic | None = None):
        self.model = model
        self.client = client or anthropic.AsyncAnthropic()

    async def parse(self, content: str | list, schema: type[T], effort: str = "medium") -> T:
        try:
            response = await self.client.messages.parse(
                model=self.model,
                max_tokens=16000,
                output_config={"effort": effort},
                messages=[{"role": "user", "content": content}],
                output_format=schema,
            )
        except anthropic.RateLimitError as e:
            raise LLMError("AI is busy right now - try again in a minute.") from e
        except anthropic.AuthenticationError as e:
            raise LLMError("AI key is invalid. Check ANTHROPIC_API_KEY.") from e
        except anthropic.BadRequestError as e:
            log.warning("LLM bad request: %s", e.message)
            raise LLMError("The AI couldn't process that input.") from e
        except anthropic.APIStatusError as e:
            log.warning("LLM API error %s (request %s)", e.status_code, getattr(e, "request_id", None))
            raise LLMError("AI service error - try again.") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Couldn't reach the AI service.") from e

        if response.stop_reason == "refusal":
            raise LLMError("The AI declined this request.")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise LLMError("The AI response was incomplete - try again.")
        return response.parsed_output
