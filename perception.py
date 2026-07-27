"""
Information filtering (Master Rulebook 1.4 / 9.4 / 9.5).

build_perception_payload() is the ONLY channel between the canonical state and
a player AI. If a fact is not in here, that player does not know it. When in
doubt the engine withholds — realistic ignorance beats omniscient narration.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import data
from .social_memory import format_social_memory_for_perception


def describe_traits(player) -> List[str]:
    return [f"{data.TRAITS[t][0]} — {data.TRAITS[t][1]}" for t in player.traits]


def build_perception_payload(state, player) -> Dict[str, Any]:
    room = state.rooms[player.location]

    visible_players = []
    for q in state.players_in(room.name, include_dead=True):
        if q.id == player.id:
            continue
        if q.health.value == "Dead":
            visible_players.append({"player": q.id, "state": "dead body"})
        elif q.hiding_in:
            continue                       # concealed (2.11) — you simply do not see them
        else:
            visible_players.append({"player": q.id, "state": q.health.value})

    payload: Dict[str, Any] = {
        "turn": state.turn,
        "you": {
            "player": player.id,
            "location": room.name,
            "room_noise_baseline": f"{room.noise}%",
            "health": player.health.value,
            "role": player.role,
            "traits": describe_traits(player),
            "objective_id": player.objective_id,
            "objective": data.OBJECTIVES[player.objective_id],
            "assassination_target": player.assassination_target,
            "inventory": [i.name for i in player.inventory],
            "inventory_limit": player.inventory_limit,
            "hiding_in": player.hiding_in,
            "clues": sorted(player.clues),
            "known_roles": {f"Player {k}": v for k, v in player.known_roles.items()},
            "objective_complete": player.objective_status.value == "Complete",
            "work_in_progress": player.progress.describe() if player.progress else None,
            "in_a_fight_with": player.fight_with,
        },
        "room": {
            "connections": list(room.connections),
            "hiding_spots": [f"{s.name} ({s.capacity - len(s.occupants)} free)"
                             for s in room.hiding_spots],
            "visible_items": [i.name for i in room.items],
            "visible_evidence": list(room.evidence),
            "power": "on" if state.power_on else "off",
        },
        "others_here": visible_players,
        "sounds_heard": list(player.sound_queue),
        "narration_since_last_turn": list(player.narration),
        "memory_recent": player.memory_log[-10:],
        "gate_open": state.gate_open,
        "social_memory": player.social_memory,
        "social_memory_formatted": format_social_memory_for_perception(
            player.social_memory, num_players=8
        ),
    }

    player.sound_queue = []
    return payload
