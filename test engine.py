"""
Mechanic-by-mechanic tests for the Labyrinth engine.

Run with:   python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from labyrinth import data                                    # noqa: E402
from labyrinth.brains import ADJACENCY, shortest_path         # noqa: E402
from labyrinth.engine import LabyrinthEngine                  # noqa: E402
from labyrinth.models import Health, Item, ObjectiveStatus    # noqa: E402


class ScriptedBrain:
    """Replays a fixed list of actions, then waits forever."""

    def __init__(self, player_id: int, script=None):
        self.id = player_id
        self.script = list(script or [])
        self.seen = []

    def decide(self, perception):
        self.seen.append(perception)
        if self.script:
            return self.script.pop(0)
        return {"action": "WAIT", "reasoning": "holding"}


class AlwaysRNG:
    """A stand-in RNG so combat and searching become deterministic in tests."""

    def __init__(self, value=0.0):
        self.value = value

    def random(self):
        return self.value

    def choice(self, seq):
        return list(seq)[0]

    def shuffle(self, seq):
        return None

    def randint(self, a, b):
        return a


def make_engine(scripts=None, seed=5, force_rng=None, max_turns=20):
    scripts = scripts or {}
    brains = [ScriptedBrain(i, scripts.get(i)) for i in range(1, 9)]
    eng = LabyrinthEngine(brains, seed=seed, max_turns=max_turns, verbose=False)
    if force_rng is not None:
        eng.state.rng = AlwaysRNG(force_rng)
    return eng


# ---------------------------------------------------------------------------
class TestMap(unittest.TestCase):

    def test_every_room_present(self):
        eng = make_engine()
        self.assertEqual(len(eng.state.rooms), 24)

    def test_connections_are_bidirectional(self):
        eng = make_engine()
        for name, room in eng.state.rooms.items():
            for other in room.connections:
                self.assertIn(name, eng.state.rooms[other].connections,
                              f"{name} -> {other} is one-way")

    def test_every_room_reachable_from_the_entrance(self):
        for target in data.ROOM_TABLE:
            self.assertTrue(shortest_path("Entrance Hall", target),
                            f"{target} is unreachable")

    def test_exit_gate_neighbours(self):
        self.assertEqual(sorted(ADJACENCY["Exit Gate"]), ["Security Office", "Vault"])


class TestSetup(unittest.TestCase):

    def test_eight_players_unique_objectives(self):
        eng = make_engine()
        objectives = sorted(p.objective_id for p in eng.state.players)
        self.assertEqual(objectives, list(range(1, 9)))

    def test_traits_match_the_appendix_table(self):
        eng = make_engine()
        for p in eng.state.players:
            self.assertEqual(p.traits, data.PLAYER_TRAITS[p.id])
        self.assertEqual(len(eng.state.player(7).traits), 3)
        self.assertEqual(len(eng.state.player(1).traits), 4)

    def test_unique_items_exist_exactly_once(self):
        eng = make_engine()
        names = []
        for room in eng.state.rooms.values():
            names += [i.name for i in room.items + room.hidden_items]
        for unique in ["Knife", "Vault Key", "Final Record", "Drive A", "Drive B", "Drive C"]:
            self.assertEqual(names.count(unique), 1, f"{unique} count wrong")
        for item_name in data.ROLE_ITEM_TO_ROLE:
            self.assertEqual(names.count(item_name), 1, f"{item_name} count wrong")

    def test_everyone_starts_in_the_entrance_hall(self):
        eng = make_engine()
        self.assertTrue(all(p.location == "Entrance Hall" for p in eng.state.players))

    def test_assassin_has_a_target(self):
        eng = make_engine()
        killer = next(p for p in eng.state.players if p.objective_id == 7)
        self.assertIsNotNone(killer.assassination_target)
        self.assertNotEqual(killer.assassination_target, killer.id)


class TestMovement(unittest.TestCase):

    def test_legal_move(self):
        eng = make_engine({1: [{"action": "MOVE", "target": "Courtyard"}]})
        eng.run_turn()
        self.assertEqual(eng.state.player(1).location, "Courtyard")

    def test_illegal_move_is_rejected(self):
        eng = make_engine({1: [{"action": "MOVE", "target": "Vault"}]})
        eng.run_turn()
        p = eng.state.player(1)
        self.assertEqual(p.location, "Entrance Hall")
        self.assertTrue(any("no direct way" in n for n in p.narration))

    def test_hiding_conceals_you_from_the_room(self):
        eng = make_engine({
            1: [{"action": "MOVE", "target": "Courtyard"},
                {"action": "HIDE", "target": "Giant tree"}],
            2: [{"action": "MOVE", "target": "Courtyard"}],
        })
        eng.run_turn()
        eng.run_turn()
        p1, p2 = eng.state.player(1), eng.state.player(2)
        self.assertEqual(p1.hiding_in, "Giant tree")
        payload = eng.state and __import__(
            "labyrinth.perception", fromlist=["x"]).build_perception_payload(eng.state, p2)
        self.assertNotIn(1, [o["player"] for o in payload["others_here"]])


class TestSearchAndItems(unittest.TestCase):

    def test_search_reveals_hidden_items(self):
        eng = make_engine({1: [{"action": "SEARCH"}]}, force_rng=0.0)
        eng.state.rooms["Entrance Hall"].hidden_items.append(Item("Test Coin"))
        eng.run_turn()
        self.assertIn("Test Coin", [i.name for i in eng.state.rooms["Entrance Hall"].items])

    def test_inventory_limit_of_four(self):
        eng = make_engine({1: [{"action": "PICKUP", "target": f"Thing {i}"} for i in range(5)]})
        room = eng.state.rooms["Entrance Hall"]
        for i in range(5):
            room.items.append(Item(f"Thing {i}"))
        for _ in range(5):
            eng.run_turn()
        self.assertEqual(len(eng.state.player(1).inventory), 4)
        self.assertTrue(any("hands are full" in n for n in eng.state.player(1).narration))

    def test_scavenger_carries_six(self):
        eng = make_engine()
        p = eng.state.player(1)
        p.role = "Scavenger"
        self.assertEqual(p.inventory_limit, 6)

    def test_claiming_a_role_item_grants_the_role_and_witnesses_learn_it(self):
        eng = make_engine({1: [{"action": "PICKUP", "target": "Magnifying Glass"}]})
        eng.state.rooms["Entrance Hall"].items.append(
            Item("Magnifying Glass", kind="role_item", unique=True,
                 data={"role": "Investigator"}))
        eng.run_turn()
        p1, p2 = eng.state.player(1), eng.state.player(2)
        self.assertEqual(p1.role, "Investigator")
        self.assertNotIn("Magnifying Glass", [i.name for i in p1.inventory])
        self.assertEqual(p2.known_roles.get(1), "Investigator")

    def test_trade_moves_an_item(self):
        eng = make_engine({1: [{"action": "TRADE", "target": "Rope", "target_player": 2}]})
        eng.state.player(1).inventory.append(Item("Rope"))
        eng.run_turn()
        self.assertIsNone(eng.state.player(1).has_item("Rope"))
        self.assertIsNotNone(eng.state.player(2).has_item("Rope"))


class TestCombat(unittest.TestCase):

    def test_knife_kills_an_unaware_target(self):
        eng = make_engine({1: [{"action": "ATTACK_KNIFE", "target_player": 2}]}, force_rng=0.0)
        eng.state.player(1).inventory.append(Item("Knife", kind="weapon", unique=True))
        eng.state.player(2).inventory.append(Item("Rope"))
        eng.run_turn()
        p2 = eng.state.player(2)
        self.assertEqual(p2.health, Health.DEAD)
        self.assertEqual(p2.objective_status, ObjectiveStatus.FAILED)
        self.assertEqual(p2.inventory, [])                    # 2.14 items drop
        self.assertIn("Rope", [i.name for i in eng.state.rooms["Entrance Hall"].items])
        self.assertTrue(any("body of Player 2" in e
                            for e in eng.state.rooms["Entrance Hall"].evidence))

    def test_knife_attack_without_a_knife_fails(self):
        eng = make_engine({1: [{"action": "ATTACK_KNIFE", "target_player": 2}]}, force_rng=0.0)
        eng.run_turn()
        self.assertEqual(eng.state.player(2).health, Health.HEALTHY)

    def test_attacking_someone_in_another_room_fails(self):
        eng = make_engine({1: [{"action": "ATTACK_KNIFE", "target_player": 2}],
                           2: [{"action": "MOVE", "target": "Courtyard"}]}, force_rng=0.0)
        eng.state.player(1).inventory.append(Item("Knife", kind="weapon"))
        eng.run_turn()
        self.assertEqual(eng.state.player(2).health, Health.HEALTHY)

    def test_unarmed_fight_resolves_over_two_turns(self):
        eng = make_engine({1: [{"action": "ATTACK_UNARMED", "target_player": 2}]}, force_rng=0.0)
        eng.run_turn()
        self.assertEqual(eng.state.player(1).fight_with, 2)
        eng.run_turn()
        healths = sorted(p.health for p in (eng.state.player(1), eng.state.player(2)))
        self.assertIn(Health.DEAD, healths)
        survivor = next(p for p in (eng.state.player(1), eng.state.player(2)) if p.alive)
        self.assertEqual(survivor.health, Health.INJURED)

    def test_push_from_the_observatory_needs_the_target_at_the_edge(self):
        eng = make_engine({1: [{"action": "PUSH_FALL", "target_player": 2}]}, force_rng=0.0)
        for pid in (1, 2):
            eng.state.player(pid).location = "Observatory"
        eng.run_turn()
        self.assertEqual(eng.state.player(2).health, Health.HEALTHY)   # not at the edge

        eng2 = make_engine({
            1: [{"action": "WAIT"}, {"action": "PUSH_FALL", "target_player": 2}],
            2: [{"action": "ROOM_INTERACT", "target": "look_through_telescope"}],
        }, force_rng=0.99)
        for pid in (1, 2):
            eng2.state.player(pid).location = "Observatory"
        eng2.run_turn()
        eng2.run_turn()
        self.assertEqual(eng2.state.player(2).health, Health.DEAD)

    def test_final_record_needs_the_right_role(self):
        script = {1: [{"action": "USE_FINAL_RECORD", "target_player": 2}] * 3}
        eng = make_engine(script, force_rng=0.0)
        p1, p2 = eng.state.player(1), eng.state.player(2)
        p1.inventory.append(Item("Final Record", kind="final_record", unique=True))
        p2.role = "Locksmith"
        p1.known_roles[2] = "Actor"                       # wrong title
        eng.run_turn()
        eng.run_turn()
        self.assertEqual(p2.health, Health.HEALTHY)
        self.assertTrue(eng.state.final_record_used)
        self.assertIsNone(p1.has_item("Final Record"))    # consumed on completion

    def test_final_record_kills_with_the_right_role(self):
        script = {1: [{"action": "USE_FINAL_RECORD", "target_player": 2}] * 3}
        eng = make_engine(script, force_rng=0.0)
        p1, p2 = eng.state.player(1), eng.state.player(2)
        p1.inventory.append(Item("Final Record", kind="final_record", unique=True))
        p2.role = "Locksmith"
        p1.known_roles[2] = "Locksmith"
        eng.run_turn()
        eng.run_turn()
        self.assertEqual(p2.health, Health.DEAD)


class TestTimedActions(unittest.TestCase):

    def test_processing_a_drive_takes_two_turns(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "process_drive"}] * 3})
        p1 = eng.state.player(1)
        p1.location = "Data Centre"
        p1.inventory.append(Item("Drive A", kind="drive", data={"letter": "A"}))
        eng.run_turn()
        self.assertFalse(eng.state.drives["A"].loaded)
        eng.run_turn()
        self.assertTrue(eng.state.drives["A"].loaded)

    def test_an_attack_interrupts_a_timed_action(self):
        eng = make_engine({
            1: [{"action": "ROOM_INTERACT", "target": "process_drive"}] * 3,
            2: [{"action": "WAIT"}, {"action": "ATTACK_UNARMED", "target_player": 1}],
        }, force_rng=0.99)
        p1, p2 = eng.state.player(1), eng.state.player(2)
        p1.location = p2.location = "Data Centre"
        p1.inventory.append(Item("Drive A", kind="drive", data={"letter": "A"}))
        eng.run_turn()
        eng.run_turn()
        self.assertFalse(eng.state.drives["A"].loaded)
        self.assertIsNone(p1.progress)

    def test_destroying_a_drive_completes_objective_four(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "destroy_drive"}] * 2})
        p1 = eng.state.player(1)
        p1.objective_id = 4
        p1.location = "Furnace"
        p1.inventory.append(Item("Drive B", kind="drive", data={"letter": "B"}))
        eng.run_turn()
        self.assertTrue(eng.state.drives["B"].destroyed)
        self.assertEqual(p1.objective_status, ObjectiveStatus.COMPLETE)

    def test_mechanism_needs_the_clue_then_completes_objective_eight(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "solve_mechanism"}] * 4})
        p1 = eng.state.player(1)
        p1.objective_id = 8
        p1.location = "Vault"
        eng.run_turn()
        self.assertFalse(p1.solved_mechanism)              # no clue yet
        p1.clues.add(data.CLUE_MECHANISM)
        eng.run_turn()
        eng.run_turn()
        self.assertTrue(p1.solved_mechanism)
        self.assertEqual(p1.objective_status, ObjectiveStatus.COMPLETE)


class TestRoomMechanics(unittest.TestCase):

    def test_generator_toggles_power_for_everyone(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "toggle_power"}]})
        eng.state.player(1).location = "Generator Room"
        eng.run_turn()
        self.assertFalse(eng.state.power_on)

    def test_cameras_need_power(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "check_cameras"}]})
        eng.state.player(1).location = "Security Office"
        eng.state.player(2).location = "Library"
        eng.state.power_on = False
        eng.run_turn()
        self.assertTrue(any("no power" in n for n in eng.state.player(1).narration))

    def test_cameras_show_watched_rooms(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "check_cameras"}]})
        eng.state.player(1).location = "Security Office"
        eng.state.player(2).location = "Library"
        eng.run_turn()
        self.assertTrue(any("Library" in n for n in eng.state.player(1).narration))

    def test_healing_an_injured_player(self):
        eng = make_engine({1: [{"action": "ROOM_INTERACT", "target": "heal"}]})
        p1 = eng.state.player(1)
        p1.location = "Medical Room"
        p1.health = Health.INJURED
        eng.run_turn()
        self.assertEqual(p1.health, Health.HEALTHY)


class TestEscapeAndScoring(unittest.TestCase):

    def test_gate_stays_shut_without_the_key(self):
        eng = make_engine({1: [{"action": "ESCAPE"}]})
        eng.state.player(1).location = "Exit Gate"
        eng.run_turn()
        self.assertFalse(eng.state.player(1).escaped)

    def test_key_opens_the_gate_permanently(self):
        eng = make_engine({1: [{"action": "ESCAPE"}], 2: [{"action": "WAIT"},
                                                          {"action": "ESCAPE"}]})
        p1, p2 = eng.state.player(1), eng.state.player(2)
        p1.location = p2.location = "Exit Gate"
        p1.inventory.append(Item("Vault Key", kind="key", unique=True))
        eng.run_turn()
        self.assertTrue(p1.escaped)
        self.assertTrue(eng.state.gate_open)
        eng.run_turn()
        self.assertTrue(p2.escaped)

    def test_drive_objective_needs_a_loaded_drive(self):
        eng = make_engine({1: [{"action": "ESCAPE"}]})
        p1 = eng.state.player(1)
        p1.objective_id = 1
        p1.location = "Exit Gate"
        p1.inventory.append(Item("Drive A", kind="drive", data={"letter": "A"}))
        eng.state.gate_open = True
        eng.run_turn()
        self.assertTrue(p1.escaped)
        self.assertEqual(p1.objective_status, ObjectiveStatus.PENDING)   # never loaded

    def test_scores(self):
        eng = make_engine()
        a, b, c, d = (eng.state.player(i) for i in (1, 2, 3, 4))
        a.escaped, a.objective_status = True, ObjectiveStatus.COMPLETE
        b.escaped = True
        c.health = Health.DEAD
        d.escaped, d.objective_status, d.exposed = True, ObjectiveStatus.COMPLETE, True
        table = {r["player"]: r["score"] for r in eng.final_results()["standings"]}
        self.assertEqual(table[1], 1.0)
        self.assertEqual(table[2], 0.0)
        self.assertEqual(table[3], -1.0)
        self.assertEqual(table[4], 0.5)

    def test_game_ends_when_everyone_is_out_or_dead(self):
        eng = make_engine()
        for p in eng.state.players:
            p.escaped = True
        self.assertTrue(eng.check_end_condition())


class TestInformationDiscipline(unittest.TestCase):

    def test_payload_never_leaks_another_players_objective(self):
        eng = make_engine()
        from labyrinth.perception import build_perception_payload
        payload = build_perception_payload(eng.state, eng.state.player(1))
        blob = str(payload)
        for other in eng.state.players[1:]:
            self.assertNotIn(data.OBJECTIVES[other.objective_id], blob.replace(
                data.OBJECTIVES[eng.state.player(1).objective_id], ""))

    def test_sound_reaches_adjacent_rooms_only_when_loud(self):
        eng = make_engine()
        loud = eng.rooms_within_hearing("Workshop", 90)
        quiet = eng.rooms_within_hearing("Storage Room", 10)
        self.assertGreater(len(loud), 1)
        self.assertEqual(list(quiet), ["Storage Room"])

    def test_a_listener_gets_precise_sound_data(self):
        eng = make_engine({2: [{"action": "ROOM_INTERACT", "target": "toggle_power"}]})
        p1, p2 = eng.state.player(1), eng.state.player(2)
        p1.role = "Listener"
        p1.location = "Workshop"
        p2.location = "Generator Room"
        eng.run_turn()
        self.assertTrue(any(s["precise"] for s in p1.sound_queue))

    def test_exposure_needs_more_than_a_third_of_the_living(self):
        eng = make_engine()
        victim = eng.state.player(1)
        for pid in (2, 3, 4, 5, 6, 7, 8):
            eng.state.player(pid).accusations[1] = victim.objective_id
            if pid > 4:
                eng.state.player(pid).health = Health.DEAD
        eng.check_objective_exposure()
        self.assertTrue(victim.exposed)

    def test_wrong_accusations_do_not_expose(self):
        eng = make_engine()
        victim = eng.state.player(1)
        wrong = 1 + (victim.objective_id % 8)
        for pid in range(2, 9):
            eng.state.player(pid).accusations[1] = wrong
        eng.check_objective_exposure()
        self.assertFalse(victim.exposed)


class TestFullGames(unittest.TestCase):

    def test_ten_seeds_all_finish_cleanly(self):
        from labyrinth.brains import HeuristicBrain
        for seed in range(1, 11):
            brains = [HeuristicBrain(i, seed=seed) for i in range(1, 9)]
            eng = LabyrinthEngine(brains, seed=seed, max_turns=45, verbose=False)
            results = eng.run()
            self.assertEqual(len(results["standings"]), 8)
            for row in results["standings"]:
                self.assertIn(row["score"], (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0))
            self.assertTrue(eng.debrief(results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
