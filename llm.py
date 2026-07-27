"""
Shared machinery for any LLM-backed player (requirement 7/8): the Player
Prompt, conversation history, sending the perception payload, and falling
back to the offline bot if a call fails, are all identical regardless of
which company's API answers.

A new provider is one small subclass that implements a single method:

    def _call_api(self, system: str, messages: list[dict]) -> str: ...

`messages` is a plain list of {"role": "user"|"assistant", "content": str}
turns — the same shape every one of these chat APIs is built around. If a
provider needs a different shape (Gemini's "model" role, for instance), the
subclass translates it right there in _call_api and nowhere else.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..actions import SCHEMA_HELP
from .base import BaseBrain
from .heuristic import HeuristicBrain


class LLMBrain(BaseBrain):
    """Base class for Anthropic/Gemini/Groq/... players. Do not use directly."""

    #: overridden by subclasses that want a different default model name
    default_model: str = ""

    def __init__(self,
                 player_id: int,
                 system_prompt: str,
                 model: Optional[str] = None,
                 max_tokens: int = 700,
                 fallback: Optional[BaseBrain] = None,
                 history_turns: int = 10):
        self.id = player_id
        self.model = model or self.default_model
        self.max_tokens = max_tokens
        self.history_turns = history_turns
        self.fallback = fallback or HeuristicBrain(player_id)
        self.system = (f"{system_prompt}\n\n---\n\nYou are Player {player_id}.\n\n"
                       f"{SCHEMA_HELP}")
        self.history: List[Dict[str, str]] = []
        self.failures = 0

    def decide(self, perception: Dict[str, Any]):
        self.history.append({"role": "user",
                             "content": json.dumps(perception, indent=2, default=str)})
        self.history = self.history[-(self.history_turns * 2):]
        try:
            text = self._call_api(self.system, self.history)
            self.history.append({"role": "assistant", "content": text})
            return text                                # parse_action handles raw json text
        except Exception as exc:
            self.failures += 1
            print(f"    [P{self.id}/{self.__class__.__name__}] API call failed "
                  f"({exc.__class__.__name__}: {exc}); falling back to the offline bot.")
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return self.fallback.decide(perception)

    # -- the only thing a subclass has to write --------------------------
    def _call_api(self, system: str, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError("Subclasses implement _call_api(system, messages).")
