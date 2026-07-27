"""
The action schema every player AI must speak (Master Rulebook 5.1-5.9).

One primary action per turn. Speaking, accusing and dropping a single item are
free actions (5.3) and may ride along with the primary action.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class ActionType:
    MOVE = "MOVE"
    SEARCH = "SEARCH"
    HIDE = "HIDE"
    UNHIDE = "UNHIDE"
    WAIT = "WAIT"
    PICKUP = "PICKUP"
    DROP = "DROP"
    TRADE = "TRADE"
    USE_ITEM = "USE_ITEM"
    HIDE_ITEM = "HIDE_ITEM"
    DESTROY_ITEM = "DESTROY_ITEM"
    ROOM_INTERACT = "ROOM_INTERACT"
    ATTACK_KNIFE = "ATTACK_KNIFE"
    ATTACK_UNARMED = "ATTACK_UNARMED"
    USE_FINAL_RECORD = "USE_FINAL_RECORD"
    PUSH_FALL = "PUSH_FALL"
    EXAMINE_BODY = "EXAMINE_BODY"
    FLEE = "FLEE"
    ESCAPE = "ESCAPE"

    ALL = {
        MOVE, SEARCH, HIDE, UNHIDE, WAIT, PICKUP, DROP, TRADE, USE_ITEM,
        HIDE_ITEM, DESTROY_ITEM, ROOM_INTERACT, ATTACK_KNIFE, ATTACK_UNARMED,
        USE_FINAL_RECORD, PUSH_FALL, EXAMINE_BODY, FLEE, ESCAPE,
    }


# Room mechanics accepted by ROOM_INTERACT (Appendix A).
MECHANICS = {
    "toggle_power",       # Generator Room
    "check_cameras",      # Security Office
    "process_drive",      # Data Centre
    "destroy_drive",      # Furnace / Boiler Room
    "solve_mechanism",    # Vault  (Objective 8)
    "open_gate",          # Exit Gate, needs the Vault Key
    "look_through_telescope",  # Observatory - puts you at the edge (6.17)
    "rest",               # Dormitory
    "heal",               # Medical Room
}

AGGRESSIVE = {ActionType.ATTACK_KNIFE, ActionType.ATTACK_UNARMED,
              ActionType.USE_FINAL_RECORD, ActionType.PUSH_FALL}


@dataclass
class Action:
    """A single declared action plus any free actions attached to it."""
    type: str = ActionType.WAIT
    target: Optional[str] = None        # room name, item name or mechanic name
    target_player: Optional[int] = None
    speech: Optional[str] = None        # free action (5.3/5.7)
    accusation: Optional[Dict[str, int]] = None   # {"player": id, "objective": 1-8}
    reveal_role: bool = False           # truthfully state your own role aloud
    reasoning: str = ""                 # private, never shown to other players
    raw: Dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        bits = [self.type]
        if self.target:
            bits.append(str(self.target))
        if self.target_player is not None:
            bits.append(f"-> P{self.target_player}")
        return " ".join(bits)


SCHEMA_HELP = """\
Reply with ONE json object and nothing else:

{
  "action": "MOVE|SEARCH|HIDE|UNHIDE|WAIT|PICKUP|DROP|TRADE|USE_ITEM|HIDE_ITEM|
             DESTROY_ITEM|ROOM_INTERACT|ATTACK_KNIFE|ATTACK_UNARMED|
             USE_FINAL_RECORD|PUSH_FALL|EXAMINE_BODY|FLEE|ESCAPE",
  "target": "room name, item name, or mechanic name (optional)",
  "target_player": 3,             // optional, the player number you act on
  "speech": "what you say out loud this turn (optional, free)",
  "accusation": {"player": 5, "objective": 7},   // optional, said out loud
  "reveal_role": false,           // true = truthfully name your own role aloud
  "reasoning": "one short private line about why"
}

Mechanics for ROOM_INTERACT: toggle_power, check_cameras, process_drive,
destroy_drive, solve_mechanism, open_gate, look_through_telescope, rest, heal.
"""


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"\d+", value)
        if m:
            return int(m.group())
    return None


def parse_action(payload: Any) -> Action:
    """
    Turn whatever the AI sent back into a validated Action.

    Accepts a dict, a json string, or a string with json embedded in prose.
    Anything unparseable becomes WAIT, which is always legal (5.11).
    """
    obj: Dict[str, Any] = {}

    if isinstance(payload, dict):
        obj = payload
    elif isinstance(payload, str):
        text = payload.strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        try:
            obj = json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    obj = json.loads(match.group())
                except Exception:
                    obj = {}
    if not isinstance(obj, dict):
        obj = {}

    raw_type = str(obj.get("action") or obj.get("type") or "WAIT").upper().strip()
    if raw_type not in ActionType.ALL:
        raw_type = ActionType.WAIT

    accusation = obj.get("accusation")
    if isinstance(accusation, dict):
        pid = _coerce_int(accusation.get("player"))
        oid = _coerce_int(accusation.get("objective"))
        accusation = {"player": pid, "objective": oid} if pid and oid else None
    else:
        accusation = None

    target = obj.get("target")
    if target is not None:
        target = str(target).strip() or None

    speech = obj.get("speech")
    if speech is not None:
        speech = str(speech).strip()[:600] or None

    return Action(
        type=raw_type,
        target=target,
        target_player=_coerce_int(obj.get("target_player")),
        speech=speech,
        accusation=accusation,
        reveal_role=bool(obj.get("reveal_role", False)),
        reasoning=str(obj.get("reasoning", ""))[:400],
        raw=obj if isinstance(obj, dict) else {},
    )
