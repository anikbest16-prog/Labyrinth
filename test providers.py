"""
Tests for the player-provider abstraction (labyrinth.brains) and the plain
PLAYERS-list configuration in run_game.py.

These do not touch the network — LLM providers are tested via a stub that
subclasses LLMBrain, exactly the way a real new provider would, to prove
the abstraction holds without needing API keys in CI.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labyrinth.brains import PLAYER_TYPES, BaseBrain, HeuristicBrain, HumanBrain  # noqa: E402
from labyrinth.brains.human import format_perception, parse_simple_command       # noqa: E402
from labyrinth.brains.llm import LLMBrain                                       # noqa: E402
from labyrinth.engine import LabyrinthEngine                                    # noqa: E402
from run_game import create_brain, make_brains                                  # noqa: E402


class StubLLMBrain(LLMBrain):
    """Stands in for any real provider: only _call_api differs, per the brief."""
    default_model = "stub-v1"

    def __init__(self, *a, reply='{"action": "WAIT", "reasoning": "stub"}',
                canned_error=None, **kw):
        super().__init__(*a, **kw)
        self.reply = reply
        self.canned_error = canned_error
        self.calls = []

    def _call_api(self, system, messages):
        self.calls.append((system, messages))
        if self.canned_error:
            raise self.canned_error
        return self.reply


class TestContract(unittest.TestCase):

    def test_every_registered_player_type_is_a_base_brain_subclass(self):
        for name, cls in PLAYER_TYPES.items():
            self.assertTrue(issubclass(cls, BaseBrain), f"{name} is not a BaseBrain")

    def test_openai_is_registered(self):
        self.assertIn("openai", PLAYER_TYPES)

    def test_base_brain_decide_is_abstract(self):
        with self.assertRaises(NotImplementedError):
            BaseBrain().decide({})

    def test_heuristic_and_stub_llm_both_expose_id_and_decide(self):
        h = HeuristicBrain(1)
        s = StubLLMBrain(2, system_prompt="be a player")
        for brain in (h, s):
            self.assertTrue(hasattr(brain, "id"))
            self.assertTrue(callable(brain.decide))


class TestCreateBrain(unittest.TestCase):

    def test_human_seat(self):
        b = create_brain("human", 1, "prompt", seed=1, leave_after=32)
        self.assertIsInstance(b, HumanBrain)
        self.assertEqual(b.id, 1)

    def test_heuristic_seat(self):
        b = create_brain("heuristic", 4, "prompt", seed=1, leave_after=32)
        self.assertIsInstance(b, HeuristicBrain)
        self.assertEqual(b.id, 4)

    def test_unknown_type_raises(self):
        with self.assertRaises(SystemExit):
            create_brain("chatgpt-4", 1, "prompt", seed=1, leave_after=32)

    def test_case_and_whitespace_are_forgiven(self):
        b = create_brain("  Heuristic  ", 2, "prompt", seed=1, leave_after=32)
        self.assertIsInstance(b, HeuristicBrain)


class TestMakeBrains(unittest.TestCase):

    def test_the_briefs_example_lineup_builds_the_right_classes_in_order(self):
        players = ["human", "heuristic", "heuristic", "human",
                  "heuristic", "heuristic", "heuristic", "heuristic"]
        brains = make_brains(players, seed=1, leave_after=32)
        self.assertEqual(len(brains), 8)
        expected = [HumanBrain, HeuristicBrain, HeuristicBrain, HumanBrain,
                   HeuristicBrain, HeuristicBrain, HeuristicBrain, HeuristicBrain]
        for brain, cls, i in zip(brains, expected, range(1, 9)):
            self.assertIsInstance(brain, cls)
            self.assertEqual(brain.id, i)

    def test_all_human(self):
        brains = make_brains(["human"] * 8, seed=1, leave_after=32)
        self.assertTrue(all(isinstance(b, HumanBrain) for b in brains))

    def test_all_heuristic(self):
        brains = make_brains(["heuristic"] * 8, seed=1, leave_after=32)
        self.assertTrue(all(isinstance(b, HeuristicBrain) for b in brains))

    def test_wrong_length_is_rejected(self):
        with self.assertRaises(SystemExit):
            make_brains(["human", "human", "human"], seed=1, leave_after=32)


class TestHumanBrainFormatting(unittest.TestCase):
    """Checks the readable print format matches the shape asked for."""

    def sample_perception(self):
        return {
            "turn": 5,
            "you": {
                "player": 4, "location": "Workshop", "health": "Healthy",
                "inventory": ["Knife"], "objective": "Recover Drive B",
                "role": None, "in_a_fight_with": None, "work_in_progress": None,
            },
            "room": {
                "visible_items": ["Magnifying Glass"],
                "connections": ["Storage Room", "Laboratory"],
                "hiding_spots": [],
            },
            "others_here": [{"player": 2, "state": "Healthy"},
                            {"player": 5, "state": "Healthy"}],
            "sounds_heard": [], "narration_since_last_turn": [], "gate_open": False,
        }

    def test_core_fields_appear_in_order(self):
        text = format_perception(self.sample_perception())
        for label in ("PLAYER 4", "Location:", "Workshop", "Health:", "Healthy",
                      "Inventory:", "Knife", "Visible Players:", "Player 2",
                      "Player 5", "Visible Items:", "Magnifying Glass",
                      "Connected Rooms:", "Storage Room", "Laboratory",
                      "Objective:", "Recover Drive B"):
            self.assertIn(label, text)
        # order matters: Location comes before Health, which comes before Inventory, etc.
        idx = {label: text.index(label) for label in
              ("Location:", "Health:", "Inventory:", "Visible Players:",
               "Visible Items:", "Connected Rooms:", "Objective:")}
        ordered = sorted(idx, key=idx.get)
        self.assertEqual(ordered, ["Location:", "Health:", "Inventory:",
                                   "Visible Players:", "Visible Items:",
                                   "Connected Rooms:", "Objective:"])

    def test_empty_inventory_shows_placeholder(self):
        p = self.sample_perception()
        p["you"]["inventory"] = []
        text = format_perception(p)
        self.assertIn("(empty)", text)


class TestSimpleCommands(unittest.TestCase):

    def test_move(self):
        self.assertEqual(parse_simple_command("move Courtyard"),
                         {"action": "MOVE", "target": "Courtyard"})

    def test_search(self):
        self.assertEqual(parse_simple_command("search"), {"action": "SEARCH"})

    def test_wait(self):
        self.assertEqual(parse_simple_command("wait"), {"action": "WAIT"})

    def test_attack(self):
        self.assertEqual(parse_simple_command("attack 3"),
                         {"action": "ATTACK_KNIFE", "target_player": 3})

    def test_fight(self):
        self.assertEqual(parse_simple_command("fight 7"),
                         {"action": "ATTACK_UNARMED", "target_player": 7})

    def test_trade(self):
        self.assertEqual(parse_simple_command("trade Rope 2"),
                         {"action": "TRADE", "target": "Rope", "target_player": 2})

    def test_say(self):
        self.assertEqual(parse_simple_command("say hello there"),
                         {"action": "WAIT", "speech": "hello there"})

    def test_escape(self):
        self.assertEqual(parse_simple_command("escape"), {"action": "ESCAPE"})

    def test_unrecognised_returns_none(self):
        self.assertIsNone(parse_simple_command("do a backflip"))

    def test_move_without_a_target_returns_none(self):
        self.assertIsNone(parse_simple_command("move"))


class TestHumanBrainDecide(unittest.TestCase):

    def _run_with_input(self, text):
        orig = builtins.input
        builtins.input = lambda prompt="": text
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                hb = HumanBrain(3)
                return hb.decide(TestHumanBrainFormatting().sample_perception())
        finally:
            builtins.input = orig

    def test_json_passes_through_untouched(self):
        result = self._run_with_input('{"action": "SEARCH"}')
        self.assertEqual(result, '{"action": "SEARCH"}')

    def test_simple_command_becomes_a_dict(self):
        result = self._run_with_input("move Storage Room")
        self.assertEqual(result, {"action": "MOVE", "target": "Storage Room"})

    def test_empty_input_is_wait(self):
        result = self._run_with_input("")
        self.assertEqual(result, {"action": "WAIT"})

    def test_free_text_becomes_speech(self):
        result = self._run_with_input("nice weather in here")
        self.assertEqual(result, {"action": "WAIT", "speech": "nice weather in here"})


class TestLLMBrainSharedMachinery(unittest.TestCase):

    def test_successful_call_is_returned_and_recorded_in_history(self):
        brain = StubLLMBrain(1, system_prompt="Player prompt goes here",
                             reply='{"action": "WAIT"}')
        out = brain.decide({"turn": 1, "you": {}, "room": {}, "others_here": []})
        self.assertEqual(out, '{"action": "WAIT"}')
        self.assertEqual(brain.history[-1], {"role": "assistant", "content": '{"action": "WAIT"}'})
        self.assertEqual(len(brain.calls), 1)

    def test_failed_call_falls_back_without_raising(self):
        fallback = HeuristicBrain(2, seed=1)
        brain = StubLLMBrain(2, system_prompt="prompt", fallback=fallback,
                             canned_error=RuntimeError("boom"))
        perception = {"turn": 1, "you": {"location": "Entrance Hall", "inventory": [],
                                          "inventory_limit": 4, "role": None,
                                          "objective_id": 4, "known_roles": {},
                                          "clues": [], "health": "Healthy"},
                      "room": {"visible_items": [], "connections": ["Courtyard"]},
                      "others_here": [], "narration_since_last_turn": [], "gate_open": False}
        out = brain.decide(perception)
        self.assertIsInstance(out, dict)
        self.assertEqual(brain.failures, 1)

    def test_a_brand_new_provider_only_needs_one_method(self):
        methods = {name for name, val in StubLLMBrain.__dict__.items()
                  if callable(val) and not name.startswith("__")}
        self.assertEqual(methods, {"_call_api"})


class TestMixedGameIntegration(unittest.TestCase):
    """The engine must run unmodified with any mix of providers in the seats."""

    def test_engine_runs_several_turns_with_a_fully_mixed_lineup(self):
        inputs = iter(['{"action":"WAIT","reasoning":"hi"}'] * 20)
        orig = builtins.input
        builtins.input = lambda prompt="": next(inputs)
        try:
            prompt = "You are a player."
            brains = [
                HumanBrain(1),
                StubLLMBrain(2, system_prompt=prompt),
                StubLLMBrain(3, system_prompt=prompt, canned_error=RuntimeError("down"),
                            fallback=HeuristicBrain(3, seed=2)),
                HeuristicBrain(4, seed=2),
                HumanBrain(5),
                StubLLMBrain(6, system_prompt=prompt),
                HeuristicBrain(7, seed=2),
                HeuristicBrain(8, seed=2),
            ]
            eng = LabyrinthEngine(brains, seed=2, max_turns=3, verbose=False)
            with contextlib.redirect_stdout(io.StringIO()):
                eng.run_turn()
                eng.run_turn()
                eng.run_turn()
        finally:
            builtins.input = orig
        self.assertEqual(eng.state.turn, 1)   # run_turn doesn't advance the counter itself
        self.assertTrue(all(p.alive for p in eng.state.players))

    def test_engine_never_imports_the_brains_package(self):
        import labyrinth.engine as engine_module
        src = Path(engine_module.__file__).read_text()
        import_lines = [ln for ln in src.splitlines()
                        if ln.strip().startswith(("import ", "from "))]
        self.assertTrue(all("brains" not in ln for ln in import_lines),
                        f"engine.py imports from brains: {import_lines}")

    def test_a_full_heuristic_game_still_runs_end_to_end(self):
        brains = make_brains(["heuristic"] * 8, seed=3, leave_after=32)
        eng = LabyrinthEngine(brains, seed=3, max_turns=45, verbose=False)
        results = eng.run()
        self.assertEqual(len(results["standings"]), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
