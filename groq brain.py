"""Groq as a player. See llm.py for everything that isn't the API call."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .llm import LLMBrain


class GroqBrain(LLMBrain):
    """Drives one player with Groq's OpenAI-compatible chat completions API."""

    default_model = "llama-3.3-70b-versatile"

    def __init__(self, player_id: int, system_prompt: str,
                 api_key: Optional[str] = None, **kwargs: Any):
        super().__init__(player_id, system_prompt, **kwargs)
        try:
            from groq import Groq
        except ImportError as exc:                     # pragma: no cover
            raise ImportError(
                "The groq package is required for GroqBrain.\n"
                "Install it with:  pip install groq"
            ) from exc
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))

    def _call_api(self, system: str, messages: List[Dict[str, str]]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return response.choices[0].message.content or ""
