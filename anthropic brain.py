"""Claude as a player. See llm.py for everything that isn't the API call."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .llm import LLMBrain


class AnthropicBrain(LLMBrain):
    """Drives one player with the Anthropic Messages API."""

    default_model = "claude-sonnet-4-6"

    def __init__(self, player_id: int, system_prompt: str,
                 api_key: Optional[str] = None, **kwargs: Any):
        super().__init__(player_id, system_prompt, **kwargs)
        try:
            import anthropic
        except ImportError as exc:                     # pragma: no cover
            raise ImportError(
                "The anthropic package is required for AnthropicBrain.\n"
                "Install it with:  pip install anthropic"
            ) from exc
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def _call_api(self, system: str, messages: List[Dict[str, str]]) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(block.text for block in response.content
                       if getattr(block, "type", "") == "text")
