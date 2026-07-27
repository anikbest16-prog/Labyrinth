"""
labyrinth.brains — every kind of player, one shared contract.

    BaseBrain        the interface: decide(perception) -> action
    HumanBrain       a person typing at the terminal (JSON or a simple command)
    HeuristicBrain   an offline bot, no API key needed
    AnthropicBrain   Claude
    GeminiBrain      Google Gemini
    GroqBrain        Groq
    OpenAIBrain      OpenAI

The engine (labyrinth/engine.py) only ever calls brain.decide(...) — it does
not import anything from this package and does not know which of the above
is behind any given seat.

PLAYER_TYPES below is the plain string -> class mapping run_game.py's
PLAYERS list is checked against ("human", "groq", "gemini", "anthropic",
"openai", "heuristic"). Adding a new provider means adding one class file
(subclassing BaseBrain, or LLMBrain if it's another chat-style API) and one
line here — nothing in the engine or in run_game.py needs to change.
"""

from __future__ import annotations

from .anthropic_brain import AnthropicBrain
from .base import BaseBrain
from .gemini_brain import GeminiBrain
from .groq_brain import GroqBrain
from .heuristic import ADJACENCY, HeuristicBrain, shortest_path, step_towards
from .human import HumanBrain
from .openai_brain import OpenAIBrain

PLAYER_TYPES = {
    "human": HumanBrain,
    "heuristic": HeuristicBrain,
    "anthropic": AnthropicBrain,
    "gemini": GeminiBrain,
    "groq": GroqBrain,
    "openai": OpenAIBrain,
}

__all__ = [
    "BaseBrain", "HumanBrain", "HeuristicBrain",
    "AnthropicBrain", "GeminiBrain", "GroqBrain", "OpenAIBrain",
    "PLAYER_TYPES", "ADJACENCY", "shortest_path", "step_towards",
]
