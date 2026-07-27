"""Gemini as a player. See llm.py for everything that isn't the API call."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .llm import LLMBrain


class GeminiBrain(LLMBrain):
    """Drives one player with Google's Gemini API."""

    default_model = "gemini-2.5-flash"

    def __init__(self, player_id: int, system_prompt: str,
                 api_key: Optional[str] = None, **kwargs: Any):
        super().__init__(player_id, system_prompt, **kwargs)
        try:
            import google.generativeai as genai
        except ImportError as exc:                     # pragma: no cover
            raise ImportError(
                "The google-generativeai package is required for GeminiBrain.\n"
                "Install it with:  pip install google-generativeai"
            ) from exc
        genai.configure(api_key=api_key or os.environ.get("GOOGLE_API_KEY")
                        or os.environ.get("GEMINI_API_KEY"))
        self._model = genai.GenerativeModel(self.model, system_instruction=self.system)

    def _call_api(self, system: str, messages: List[Dict[str, str]]) -> str:
        # Gemini's chat format is almost the same shape as everyone else's,
        # except the assistant's turns are labelled "model" instead of
        # "assistant" and content lives under "parts". That translation is
        # the only Gemini-specific thing here.
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [m["content"]]} for m in messages]
        response = self._model.generate_content(
            contents,
            generation_config={"max_output_tokens": self.max_tokens},
        )
        return response.text
