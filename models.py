"""Data structures for the canonical game state (Master Rulebook 9.2)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from . import data


class Health(str, Enum):
    HEALTHY = "Healthy"
    INJURED = "Injured"
    DEAD = "Dead"


class ObjectiveStatus(str, Enum):
    PENDING = "Pending"
    COMPLETE = "Complete"
    FAILED = "Failed"


@dataclass
class Item:
    """0.5 - a physical object."""
    name: str
    kind: str = "misc"          # weapon | role_item | drive | key | final_record | consumable | misc
    unique: bool = False
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.name


@dataclass
class HidingSpot:
    """3.6 - a named spot with a fixed capacity."""
    name: str
    capacity: int
    occupants: List[int] = field(default_factory=list)

    @property
    def full(self) -> bool:
        return len(self.occupants) >= self.capacity


@dataclass
class Room:
    """0.2 - a discrete location."""
    name: str
    noise: int = 0
    notes: str = ""
    connections: List[str] = field(default_factory=list)
    hiding_spots: List[HidingSpot] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)          # openly visible (4.17)
    hidden_items: List[Item] = field(default_factory=list)   # need a search (3.4)
    evidence: List[str] = field(default_factory=list)        # 0.12 / 3.13
    mechanic_state: Dict[str, Any] = field(default_factory=dict)

    def spot(self, name: str) -> Optional[HidingSpot]:
        for s in self.hiding_spots:
            if s.name.lower() == name.lower():
                return s
        return None

    def free_spot(self) -> Optional[HidingSpot]:
        for s in self.hiding_spots:
            if not s.full:
                return s
        return None

    def find_item(self, name: str, hidden: bool = False) -> Optional[Item]:
        pool = self.hidden_items if hidden else self.items
        for it in pool:
            if it.name.lower() == name.lower():
                return it
        return None


@dataclass
class Progress:
    """A multi-turn / interruptible action in flight (5.17)."""
    kind: str
    seconds_left: int
    room: str
    target: Optional[str] = None      # item name, mechanic name, or player id as str

    def describe(self) -> str:
        return f"{self.kind} ({self.seconds_left}s remaining)"


@dataclass
class Player:
    """0.1 - a participant."""
    id: int
    name: str
    location: str = "Entrance Hall"
    health: Health = Health.HEALTHY
    inventory: List[Item] = field(default_factory=list)
    objective_id: int = 0
    objective_status: ObjectiveStatus = ObjectiveStatus.PENDING
    exposed: bool = False
    role: Optional[str] = None
    traits: List[int] = field(default_factory=list)
    hiding_in: Optional[str] = None
    memory_log: List[str] = field(default_factory=list)
    known_roles: Dict[int, str] = field(default_factory=dict)   # verified knowledge only
    role_beliefs: Dict[int, str] = field(default_factory=dict)  # what they were told (may be a lie)
    clues: Set[str] = field(default_factory=set)
    assassination_target: Optional[int] = None
    escaped: bool = False
    finish_turn: Optional[int] = None
    progress: Optional[Progress] = None
    fight_with: Optional[int] = None
    fight_seconds: int = 0
    sound_queue: List[Dict[str, Any]] = field(default_factory=list)
    speech_queue: List[Dict[str, Any]] = field(default_factory=list)
    narration: List[str] = field(default_factory=list)
    accusations: Dict[int, int] = field(default_factory=dict)   # target id -> guessed objective id
    solved_mechanism: bool = False
    destroyed_drive: bool = False
    kills: List[int] = field(default_factory=list)
    brain: Any = None
    ai_context: List[Dict[str, Any]] = field(default_factory=list)
    last_action_summary: str = ""
    social_memory: Dict[str, List[Any]] = field(default_factory=dict)  # persistent social tracking

    # -- helpers ------------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self.health != Health.DEAD

    @property
    def active(self) -> bool:
        """Still taking turns: alive and not yet out of the labyrinth."""
        return self.alive and not self.escaped

    @property
    def inventory_limit(self) -> int:
        return (data.SCAVENGER_INVENTORY_LIMIT if self.role == "Scavenger"
                else data.BASE_INVENTORY_LIMIT)

    def has_item(self, name: str) -> Optional[Item]:
        for it in self.inventory:
            if it.name.lower() == name.lower():
                return it
        return None

    def take(self, name: str) -> Optional[Item]:
        it = self.has_item(name)
        if it:
            self.inventory.remove(it)
        return it

    def remember(self, text: str, turn: int) -> None:
        self.memory_log.append(f"T{turn}: {text}")


@dataclass
class DriveState:
    """Appendix D - drives must be loaded at the Data Centre to count."""
    name: str
    loaded: bool = False
    destroyed: bool = False


@dataclass
class GameState:
    turn: int = 1
    rooms: Dict[str, Room] = field(default_factory=dict)
    players: List[Player] = field(default_factory=list)
    drives: Dict[str, DriveState] = field(default_factory=dict)
    power_on: bool = True
    gate_open: bool = False
    key_model: str = "permanent"        # "permanent" or "consumed" (Engine Prompt 4.11)
    final_record_used: bool = False
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    turn_events: List[Dict[str, Any]] = field(default_factory=list)
    game_over: bool = False
    rng: random.Random = field(default_factory=random.Random)
    max_turns: int = 60

    # -- helpers ------------------------------------------------------------
    def player(self, pid: int) -> Optional[Player]:
        for p in self.players:
            if p.id == pid:
                return p
        return None

    def room(self, name: str) -> Optional[Room]:
        return self.rooms.get(name)

    def players_in(self, room_name: str, include_dead: bool = False) -> List[Player]:
        return [p for p in self.players
                if p.location == room_name and not p.escaped
                and (include_dead or p.alive)]

    def active_players(self) -> List[Player]:
        return [p for p in self.players if p.active]

    def living_players(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def log(self, kind: str, **payload: Any) -> Dict[str, Any]:
        event = {"turn": self.turn, "kind": kind, **payload}
        self.event_log.append(event)
        self.turn_events.append(event)
        return event
