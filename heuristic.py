"""
The offline player: no API key, no network, no hidden information — just a
reasonably competent bot that chases its objective and heads for the exit.

Also exports the map-knowledge helpers (ADJACENCY, shortest_path) that both
this bot and the LLM brains rely on to describe/plan routes through the
labyrinth (a person walking the halls learns the layout; that is not hidden
information under 1.4).
"""

from __future__ import annotations

import random
from collections import deque
from typing import Any, Dict, List, Optional

from .. import data
from .base import BaseBrain

# ---------------------------------------------------------------------------
# shared map knowledge (a person walking the labyrinth learns the layout)
# ---------------------------------------------------------------------------
def build_adjacency() -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {name: [] for name in data.ROOM_TABLE}
    for src, dests in data.RAW_CONNECTIONS.items():
        for dst in dests:
            if dst not in adj[src]:
                adj[src].append(dst)
            if src not in adj[dst]:
                adj[dst].append(src)
    return adj


ADJACENCY = build_adjacency()


def shortest_path(start: str, goal: str) -> List[str]:
    """BFS. Returns [start, ..., goal] or [] if unreachable."""
    if start == goal:
        return [start]
    seen = {start}
    queue = deque([[start]])
    while queue:
        path = queue.popleft()
        for nxt in ADJACENCY.get(path[-1], []):
            if nxt in seen:
                continue
            seen.add(nxt)
            new = path + [nxt]
            if nxt == goal:
                return new
            queue.append(new)
    return []


def step_towards(start: str, goal: str) -> Optional[str]:
    path = shortest_path(start, goal)
    return path[1] if len(path) > 1 else None


# ---------------------------------------------------------------------------
# OFFLINE BOT
# ---------------------------------------------------------------------------
DRIVE_SPAWNS = ["Laboratory", "Maintenance Tunnels", "Hidden Chamber",
                "Water Reservoir", "Armoury", "Kitchen/Dining Hall"]
KNIFE_SPAWNS = ["Kitchen/Dining Hall", "Workshop", "Armoury",
                "Storage Room", "Laboratory"]
ROLE_ITEM_NAMES = set(data.ROLE_ITEM_TO_ROLE)


class HeuristicBrain(BaseBrain):
    """A competent-but-simple player. No API calls, no hidden information."""

    def __init__(self, player_id: int, seed: int = 0, leave_after_turn: int = 32):
        self.id = player_id
        self.rng = random.Random(seed * 100 + player_id)
        self.leave_after = leave_after_turn
        self.seen_items: Dict[str, str] = {}      # item name -> room where last seen
        self.searched: Dict[str, int] = {}
        self.visited: set = set()
        self.drive_loaded = False
        self.gate_known_open = False

    # -- bookkeeping ----------------------------------------------------
    def observe(self, p: Dict[str, Any]) -> None:
        me, room = p["you"], p["room"]
        self.visited.add(me["location"])
        for item in room["visible_items"]:
            self.seen_items[item] = me["location"]
        for line in p.get("narration_since_last_turn", []):
            if "finishes loading" in line:
                self.drive_loaded = True
        self.gate_known_open = p.get("gate_open", False)

    def searches_here(self, room_name: str) -> int:
        return self.searched.get(room_name, 0)

    def do_search(self, room_name: str) -> Dict[str, Any]:
        self.searched[room_name] = self.searches_here(room_name) + 1
        return {"action": "SEARCH", "reasoning": f"looking for what {room_name} is hiding"}

    def go(self, here: str, there: str, why: str) -> Dict[str, Any]:
        nxt = step_towards(here, there)
        if not nxt:
            return {"action": "WAIT", "reasoning": "no route"}
        return {"action": "MOVE", "target": nxt, "reasoning": why}

    def seek(self, me: Dict[str, Any], item: str, candidate_rooms: List[str],
             why: str) -> Dict[str, Any]:
        """Fetch a known item, or search likely rooms for it."""
        here = me["location"]
        if item in self.seen_items:
            room = self.seen_items[item]
            if room == here:
                return {"action": "PICKUP", "target": item, "reasoning": why}
            return self.go(here, room, why)
        if here in candidate_rooms and self.searches_here(here) < 3:
            return self.do_search(here)
        unsearched = [r for r in candidate_rooms if self.searches_here(r) < 3]
        if unsearched:
            unsearched.sort(key=lambda r: len(shortest_path(here, r)) or 99)
            return self.go(here, unsearched[0], why)
        return self.wander(here)

    def wander(self, here: str) -> Dict[str, Any]:
        options = [r for r in ADJACENCY[here] if r not in self.visited]
        if not options:
            options = ADJACENCY[here]
        return {"action": "MOVE", "target": self.rng.choice(options),
                "reasoning": "learning the layout"}

    # -- the decision ---------------------------------------------------
    def decide(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        self.observe(perception)
        me = perception["you"]
        room = perception["room"]
        here = me["location"]
        turn = perception["turn"]
        oid = me.get("objective_id", 0)
        inv = me["inventory"]
        others = [o["player"] for o in perception["others_here"] if o["state"] != "dead body"]

        # 0. brawls
        if me.get("in_a_fight_with") is not None:
            if me["health"] == "Injured":
                return {"action": "FLEE", "reasoning": "losing this"}
            return {"action": "ATTACK_UNARMED", "target_player": me["in_a_fight_with"],
                    "reasoning": "finish it"}

        # 1. free social noise — occasionally accuse someone out loud (1.7)
        extras: Dict[str, Any] = {}
        if others and self.rng.random() < 0.10:
            extras["accusation"] = {"player": self.rng.choice(others),
                                    "objective": self.rng.randint(1, 8)}
            extras["speech"] = "You have been acting strangely. I know what you are after."
        elif others and self.rng.random() < 0.20:
            extras["speech"] = "What did you find? Tell me your role and I will tell you mine."
        # answer someone who asked about roles
        for line in perception.get("narration_since_last_turn", []):
            if "role" in line.lower() and me["role"] and self.rng.random() < 0.5:
                extras["reveal_role"] = True

        # 2. opportunism — a role or the key lying in front of you is worth the turn
        grab = self.opportunity(me, room)
        if grab:
            grab.update({k: v for k, v in extras.items() if k not in grab})
            return grab

        decision = self._objective_move(perception, me, room, here, turn, oid, inv, others)
        decision.update({k: v for k, v in extras.items() if k not in decision})
        return decision

    def opportunity(self, me: Dict[str, Any], room: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Pick up obviously valuable things, and glance around a new room."""
        if len(me["inventory"]) >= me["inventory_limit"]:
            return None
        visible = room["visible_items"]
        if "Vault Key" in visible and "Vault Key" not in me["inventory"]:
            return {"action": "PICKUP", "target": "Vault Key", "reasoning": "that is the way out"}
        if not me["role"]:
            for item in visible:
                if item in ROLE_ITEM_NAMES:
                    return {"action": "PICKUP", "target": item,
                            "reasoning": "whatever this is, it is worth having"}
        here = me["location"]
        if self.searches_here(here) == 0 and self.rng.random() < 0.30:
            return self.do_search(here)
        return None

    def _objective_move(self, perception, me, room, here, turn, oid, inv, others) -> Dict[str, Any]:
        ready = self.ready_to_leave(me, turn, oid)

        # --- endgame: key, gate, out
        if ready:
            if here == "Exit Gate":
                if perception.get("gate_open") or "Vault Key" in inv:
                    return {"action": "ESCAPE", "reasoning": "done here"}
                return {"action": "WAIT", "reasoning": "waiting for someone to open the gate"}
            if perception.get("gate_open") or "Vault Key" in inv:
                return self.go(here, "Exit Gate", "heading out")
            if here == "Vault":
                if "Vault Key" in room["visible_items"]:
                    return {"action": "PICKUP", "target": "Vault Key", "reasoning": "the way out"}
                if self.searches_here(here) < 3:
                    return self.do_search(here)
                return self.go(here, "Exit Gate", "someone else must have the key")
            if self.searches_here("Vault") < 3:
                return self.go(here, "Vault", "the key is in the Vault")
            return self.go(here, "Exit Gate", "wait at the gate")

        # --- objective work
        if oid in (1, 2, 3):
            letter = "ABC"[oid - 1]
            drive = f"Drive {letter}"
            if drive not in inv:
                return self.seek(me, drive, DRIVE_SPAWNS, f"I need {drive}")
            if not self.drive_loaded:
                if here == "Data Centre":
                    return {"action": "ROOM_INTERACT", "target": "process_drive",
                            "reasoning": "load the drive or it is worthless"}
                return self.go(here, "Data Centre", "the drive must be read")
            return self.go(here, "Vault", "objective done, now the key")

        if oid == 4:
            carried = next((i for i in inv if i.startswith("Drive ")), None)
            if not carried:
                for letter in "ABC":
                    if f"Drive {letter}" in self.seen_items:
                        return self.seek(me, f"Drive {letter}", DRIVE_SPAWNS, "a drive to burn")
                return self.seek(me, "Drive A", DRIVE_SPAWNS, "any drive will do")
            if here in ("Furnace", "Boiler Room"):
                return {"action": "ROOM_INTERACT", "target": "destroy_drive",
                        "reasoning": "burn it"}
            return self.go(here, "Furnace", "to the furnace")

        if oid == 5:
            clues = set(me["clues"])
            if "Final Record" in inv:
                return self.go(here, "Vault", "I have it — now the key")
            if data.CLUE_LIBRARY not in clues:
                if here == "Library":
                    return self.do_search(here)
                return self.go(here, "Library", "start with the books")
            if data.CLUE_ARCHIVE not in clues:
                if here == "Archive":
                    return self.do_search(here)
                return self.go(here, "Archive", "the note pointed to the archive")
            if here == "Hidden Shrine":
                if "Final Record" in room["visible_items"]:
                    return {"action": "PICKUP", "target": "Final Record", "reasoning": "there it is"}
                return self.do_search(here)
            return self.go(here, "Hidden Shrine", "below the tunnels")

        if oid == 6:
            if me["known_roles"]:
                return self.go(here, "Vault", "I know one of them — time to leave")
            if others:
                return {"action": "WAIT",
                        "speech": "Show me what you found and I will trust you. What is your role?",
                        "reasoning": "someone here may talk"}
            busy = ["Courtyard", "Entrance Hall", "Storage Room", "Library"]
            return self.go(here, self.rng.choice(busy), "find people to talk to")

        if oid == 7:
            target = me.get("assassination_target")
            if target in others:
                if "Knife" in inv:
                    return {"action": "ATTACK_KNIFE", "target_player": target,
                            "reasoning": "clean and quick"}
                if me["health"] == "Healthy" and len(others) == 1:
                    return {"action": "ATTACK_UNARMED", "target_player": target,
                            "reasoning": "no witnesses, no knife"}
            if "Knife" not in inv:
                return self.seek(me, "Knife", KNIFE_SPAWNS, "I need a blade")
            hunting = ["Courtyard", "Storage Room", "Library", "Entrance Hall", "Dormitory"]
            return self.go(here, self.rng.choice(hunting), "hunting")

        if oid == 8:
            if data.CLUE_MECHANISM not in set(me["clues"]):
                if here in ("Hidden Chamber", "Vault") and self.searches_here(here) < 3:
                    return self.do_search(here)
                return self.go(here, "Hidden Chamber", "the diagram must be somewhere")
            if here == "Vault":
                return {"action": "ROOM_INTERACT", "target": "solve_mechanism",
                        "reasoning": "work the dials"}
            return self.go(here, "Vault", "to the mechanism")

        return self.wander(here)

    def ready_to_leave(self, me: Dict[str, Any], turn: int, oid: int) -> bool:
        if me.get("objective_complete"):
            return True
        if oid in (1, 2, 3):
            letter = "ABC"[oid - 1]
            if f"Drive {letter}" in me["inventory"] and self.drive_loaded:
                return True
        if oid == 5 and "Final Record" in me["inventory"]:
            return True
        if oid == 6 and me["known_roles"]:
            return True
        return turn >= self.leave_after


