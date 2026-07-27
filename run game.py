#!/usr/bin/env python3
"""
Run a game of LABYRINTH.

To choose who controls each of the 8 seats, edit the PLAYERS list right below
this docstring. That is the only thing you need to change. Everything else
about running the game (the engine, the rules, how a turn resolves) stays
exactly the same no matter what you put in that list.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List

from labyrinth import LabyrinthEngine
from labyrinth.brains import PLAYER_TYPES, HeuristicBrain

# ============================================================================
# PLAYER CONFIGURATION
# ----------------------------------------------------------------------------
# One entry per player, in order (Player 1 first, Player 8 last).
# Valid values: "human", "heuristic", "anthropic", "gemini", "groq", "openai"
#
# Examples:
#
#   All human:
#     PLAYERS = ["human"] * 8
#
#   All Groq:
#     PLAYERS = ["groq"] * 8
#
#   Mixed:
#     PLAYERS = ["human", "groq", "gemini", "human",
#                "heuristic", "anthropic", "groq", "openai"]
# ============================================================================
PLAYERS = [
    "heuristic",
    "heuristic",
    "heuristic",
    "heuristic",
    "heuristic",
    "heuristic",
    "heuristic",
    "heuristic",
]

HERE = Path(__file__).resolve().parent
PLAYER_PROMPT_PATH = HERE / "rules" / "03_PLAYER_PROMPT.md"

FALLBACK_PLAYER_PROMPT = """You are one player inside LABYRINTH, a social deduction,
stealth and survival game. You know only what your character perceives. Maximise your
final score: +1 complete your objective then escape, 0 escape without it, -1 die,
-0.5 if more than a third of living players correctly name your objective.
Never invent information you were not given."""


def load_player_prompt() -> str:
    """Every LLM seat gets this exact same text as its system prompt (requirement 3)."""
    if PLAYER_PROMPT_PATH.exists():
        return PLAYER_PROMPT_PATH.read_text(encoding="utf-8")
    print(f"[warn] {PLAYER_PROMPT_PATH} not found; using the short built-in prompt.")
    return FALLBACK_PLAYER_PROMPT


def create_brain(player_type: str, player_id: int, prompt: str,
                 seed: int, leave_after: int) -> Any:
    """
    One player type -> one brain instance for that seat.

    This is the entire "provider creation" step: look the name up in
    PLAYER_TYPES (a plain dict in labyrinth/brains/__init__.py) and construct
    it. Every LLM brain (anthropic/gemini/groq/openai/...) is built the exact
    same way — same Player Prompt, same offline fallback — so a brand new
    provider only ever needs a new class, never a change here.
    """
    player_type = player_type.strip().lower()
    if player_type not in PLAYER_TYPES:
        raise SystemExit(f"Unknown player type '{player_type}' for Player {player_id}. "
                         f"Choices: {sorted(PLAYER_TYPES)}")
    cls = PLAYER_TYPES[player_type]

    if player_type == "human":
        return cls(player_id)
    if player_type == "heuristic":
        return cls(player_id, seed=seed, leave_after_turn=leave_after)

    # Every other registered type is an LLM brain: same prompt, same fallback.
    fallback = HeuristicBrain(player_id, seed=seed, leave_after_turn=leave_after)
    return cls(player_id, system_prompt=prompt, fallback=fallback)


def make_brains(players: List[str], seed: int, leave_after: int) -> List[Any]:
    if len(players) != 8:
        raise SystemExit(f"PLAYERS must have exactly 8 entries, got {len(players)}: {players}")
    prompt = load_player_prompt()
    return [create_brain(player_type, i, prompt, seed, leave_after)
            for i, player_type in enumerate(players, start=1)]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run a game of Labyrinth. Edit the PLAYERS list at the "
                    "top of run_game.py to choose who controls each seat.")
    ap.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    ap.add_argument("--turns", type=int, default=60, help="turn limit (default 60)")
    ap.add_argument("--key-model", choices=["permanent", "consumed"], default="permanent",
                    help="Vault Key behaviour (Engine Prompt 4.11)")
    ap.add_argument("--leave-after", type=int, default=32,
                    help="turn after which heuristic bots head for the exit regardless")
    ap.add_argument("--quiet", action="store_true", help="do not print the live transcript")
    ap.add_argument("--out", default="", help="directory to write transcript + results")
    args = ap.parse_args()

    try:
        brains = make_brains(PLAYERS, args.seed, args.leave_after)
    except ImportError as exc:
        print(f"error: {exc}")
        return 2
    except Exception as exc:                        # e.g. a missing API key
        print(f"error building players: {exc}")
        return 2

    print("Seats: " + ", ".join(f"P{i}={t}" for i, t in enumerate(PLAYERS, start=1)))
    engine = LabyrinthEngine(brains, seed=args.seed, max_turns=args.turns,
                             key_model=args.key_model, verbose=not args.quiet)
    results = engine.run()
    debrief = engine.debrief(results)
    print(debrief)

    if args.out:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "transcript.txt").write_text(
            "\n".join(engine.transcript) + "\n" + debrief, encoding="utf-8")
        (outdir / "results.json").write_text(
            json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {outdir/'transcript.txt'} and {outdir/'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
