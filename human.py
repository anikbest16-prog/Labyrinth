"""
A human being plays this seat from the terminal.

The engine hands this brain exactly the same perception payload it hands any
AI. This module turns that payload into something readable, asks the person
for an action, and hands back either a JSON string or a plain dict — exactly
what every other brain returns. The engine's own parse_action() (unchanged)
is what turns that into the Action object every brain's output becomes; the
human seat is not a special case anywhere else in the pipeline.

Two ways to answer the prompt:
  - JSON, e.g.  {"action": "MOVE", "target": "Courtyard"}
  - a simple command, e.g.  move Courtyard   /   search   /   attack 3

Typing "help" shows the list of simple commands.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import BaseBrain

BAR = "=" * 36

HELP_TEXT = """\
Simple commands (or type a JSON action instead):
  move <room>            go to a connected room
  search                 search the room you're in
  hide [<spot>]          hide (in a named spot, or any free one)
  unhide                 come out of hiding
  wait                   do nothing this turn
  pickup <item>          take a visible item
  drop <item>            put down a carried item
  use <item>             use a carried item
  stash <item>           hide a carried item in this room
  trade <item> <player>  hand an item to another player here
  interact <mechanic>    e.g. interact toggle_power / process_drive / open_gate
  attack <player>        knife attack (needs a knife)
  fight <player>         start an unarmed fight
  push <player>          push them from the Observatory edge
  record <player>        use the Final Record on them
  examine [<player>]     examine a body in this room
  flee [<room>]          break away and move, ignoring the usual route
  escape                 leave through the Exit Gate
  say <message>          speak aloud this turn (no other action)
  reveal                 truthfully state your own role aloud
  accuse <player> <objective#>   accuse someone of an objective, aloud
  help                   show this list again
"""


def format_perception(perception: Dict[str, Any]) -> str:
    """A plain, readable rendering of the same payload every AI brain gets."""
    you = perception.get("you", {}) or {}
    room = perception.get("room", {}) or {}
    others = perception.get("others_here", []) or []

    lines: List[str] = [BAR, f"PLAYER {you.get('player', '?')}", BAR]

    lines.append("Location:")
    lines.append(str(you.get("location", "?")))

    lines.append("Health:")
    lines.append(str(you.get("health", "?")))

    lines.append("Inventory:")
    inv = you.get("inventory") or []
    lines.extend(inv if inv else ["(empty)"])

    lines.append("Visible Players:")
    alive = [o for o in others if o.get("state") != "dead body"]
    lines.extend([f"Player {o['player']}" for o in alive] if alive else ["(none)"])

    bodies = [o for o in others if o.get("state") == "dead body"]
    if bodies:
        lines.append("Bodies Here:")
        lines.extend(f"Player {o['player']}" for o in bodies)

    lines.append("Visible Items:")
    items = room.get("visible_items") or []
    lines.extend(items if items else ["(none)"])

    lines.append("Connected Rooms:")
    conns = room.get("connections") or []
    lines.extend(conns if conns else ["(none)"])

    lines.append("Objective:")
    lines.append(str(you.get("objective", "?")))

    # Extra context beyond the core example — same plain style, behind a
    # divider, so a human has enough to actually play (sounds, recent
    # narration, role, whether a fight or timed task is underway).
    extra: List[str] = []
    if you.get("role"):
        extra += ["Role:", you["role"]]
    if you.get("in_a_fight_with") is not None:
        extra += ["Fighting:", f"Player {you['in_a_fight_with']}"]
    if you.get("work_in_progress"):
        extra += ["In Progress:", you["work_in_progress"]]
    hiding_spots = room.get("hiding_spots") or []
    if hiding_spots:
        extra.append("Hiding Spots:")
        extra.extend(hiding_spots)
    sounds = perception.get("sounds_heard") or []
    if sounds:
        extra.append("Sounds Heard:")
        for s in sounds:
            tag = " (precise)" if s.get("precise") else ""
            extra.append(f"{s.get('loudness', '?')} from {s.get('origin', '?')}, "
                        f"{s.get('distance', '?')} room(s) away{tag}")
    narration = perception.get("narration_since_last_turn") or []
    if narration:
        extra.append("Since Last Turn:")
        extra.extend(f"- {n}" for n in narration)
    if perception.get("gate_open"):
        extra.append("The Exit Gate stands open.")

    if extra:
        lines.append(BAR)
        lines.extend(extra)

    lines.append(BAR)
    return "\n".join(lines)


def _as_int(text: str) -> Optional[int]:
    try:
        return int(text.strip())
    except (TypeError, ValueError):
        return None


def parse_simple_command(text: str) -> Optional[Dict[str, Any]]:
    """Translate one line like "move Courtyard" into an action dict, or None
    if it isn't one of the simple commands (caller falls back to speech)."""
    parts = text.strip().split(None, 1)
    if not parts:
        return None
    verb = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if verb in ("move", "go") and rest:
        return {"action": "MOVE", "target": rest}
    if verb in ("search", "look"):
        return {"action": "SEARCH"}
    if verb == "wait":
        return {"action": "WAIT"}
    if verb == "hide":
        return {"action": "HIDE", "target": rest or None}
    if verb == "unhide":
        return {"action": "UNHIDE"}
    if verb in ("pickup", "take", "grab") and rest:
        return {"action": "PICKUP", "target": rest}
    if verb == "drop" and rest:
        return {"action": "DROP", "target": rest}
    if verb == "use" and rest:
        return {"action": "USE_ITEM", "target": rest}
    if verb in ("stash", "hideitem") and rest:
        return {"action": "HIDE_ITEM", "target": rest}
    if verb == "destroy" and rest:
        return {"action": "DESTROY_ITEM", "target": rest}
    if verb in ("interact", "room") and rest:
        return {"action": "ROOM_INTERACT", "target": rest}
    if verb == "escape":
        return {"action": "ESCAPE"}
    if verb == "flee":
        return {"action": "FLEE", "target": rest or None}
    if verb in ("examine", "inspect"):
        pid = _as_int(rest)
        return {"action": "EXAMINE_BODY", "target_player": pid}
    if verb in ("trade", "give"):
        bits = rest.split()
        if len(bits) >= 2:
            pid = _as_int(bits[-1])
            item = " ".join(bits[:-1])
            if pid is not None and item:
                return {"action": "TRADE", "target": item, "target_player": pid}
        return None
    if verb in ("attack", "knife", "stab"):
        pid = _as_int(rest)
        return {"action": "ATTACK_KNIFE", "target_player": pid} if pid is not None else None
    if verb in ("fight", "punch", "unarmed"):
        pid = _as_int(rest)
        return {"action": "ATTACK_UNARMED", "target_player": pid} if pid is not None else None
    if verb == "push":
        pid = _as_int(rest)
        return {"action": "PUSH_FALL", "target_player": pid} if pid is not None else None
    if verb in ("record", "write"):
        pid = _as_int(rest)
        return {"action": "USE_FINAL_RECORD", "target_player": pid} if pid is not None else None
    if verb == "say" and rest:
        return {"action": "WAIT", "speech": rest}
    if verb == "reveal":
        return {"action": "WAIT", "reveal_role": True}
    if verb == "accuse":
        bits = rest.split()
        if len(bits) >= 2:
            pid, oid = _as_int(bits[0]), _as_int(bits[1])
            if pid is not None and oid is not None:
                return {"action": "WAIT", "accusation": {"player": pid, "objective": oid}}
        return None
    return None


class HumanBrain(BaseBrain):
    """Prints the perception in a readable format, reads one line, returns an action."""

    def __init__(self, player_id: int):
        self.id = player_id

    def decide(self, perception: Dict[str, Any]):
        print("\n" + format_perception(perception))
        print("Enter your action (or 'help' for command examples):")
        while True:
            raw = input("> ").strip()
            if not raw:
                return {"action": "WAIT"}
            if raw.lower() in ("help", "?"):
                print(HELP_TEXT)
                continue
            if raw.startswith("{"):
                return raw                          # parse_action() handles JSON text
            cmd = parse_simple_command(raw)
            if cmd is not None:
                return cmd
            # not JSON, not a recognised command -- treat it as something said
            # aloud while waiting, so a human can just talk without memorising syntax
            return {"action": "WAIT", "speech": raw}
