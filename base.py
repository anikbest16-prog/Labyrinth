"""
The one contract every player must satisfy, human or AI (requirement 4/9 of
the brief): the engine only ever calls

    brain.decide(perception) -> action

where `action` may be a dict already matching the action schema, or a raw
string (JSON, or JSON embedded in prose) that labyrinth.actions.parse_action
knows how to clean up. Nothing else about a brain matters to the engine.
"""

from __future__ import annotations

from typing import Any, Dict, Union

Action = Union[Dict[str, Any], str]


class BaseBrain:
    """Subclass this and implement decide(). That's the whole interface."""

    id: int

    def decide(self, perception: Dict[str, Any]) -> Action:
        raise NotImplementedError("Every brain must implement decide(perception).")
