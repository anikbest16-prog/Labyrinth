"""
Static game data for LABYRINTH.

Everything in this module is transcribed directly from the Master Rulebook
(Appendix A: rooms & map, Appendix E: traits, Chapter 7: roles,
Chapter 8: objectives, 5.17: action durations, Appendix F: items).

Nothing here changes at runtime.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# TIME MODEL
# ---------------------------------------------------------------------------
# The rulebook specifies action durations in seconds (5.17). We map that onto
# discrete turns: each turn grants TURN_SECONDS of progress on a timed action.
TURN_SECONDS = 15

DURATIONS = {                      # Master Rulebook 5.17, in seconds
    "move": 5,
    "speak": 0,
    "search": 15,
    "hide": 5,
    "pickup": 3,
    "drop": 3,
    "trade": 3,
    "simple_mechanic": 10,
    "generator_toggle": 10,
    "process_drive": 20,           # interruptible
    "destroy_drive": 15,           # interruptible
    "lockpick": 15,                # interruptible
    "lockpick_locksmith": 7,       # interruptible
    "solve_mechanism": 30,         # interruptible (Objective 8, Vault chain)
    "knife_attack": 3,
    "unarmed_fight": 30,           # 20-40 sec, multi-turn
    "write_final_record": 30,      # interruptible
}

INTERRUPTIBLE = {
    "process_drive",
    "destroy_drive",
    "lockpick",
    "lockpick_locksmith",
    "solve_mechanism",
    "write_final_record",
}

# ---------------------------------------------------------------------------
# APPENDIX A - ROOM DIRECTORY
# name: (baseline noise %, {hiding spot name: capacity}, notes)
# ---------------------------------------------------------------------------
ROOM_TABLE = {
    "Entrance Hall":      (50,  {},                                              "Starting point for all players"),
    "Library":            (10,  {"Bookshelves": 3, "Behind librarian desk": 1},  "First Final Record clue"),
    "Archive":            (30,  {"Shelves": 2},                                  "Second Final Record clue"),
    "Observatory":        (5,   {},                                              "High point - fall-damage kill site (6.17)"),
    "Security Office":    (45,  {"Secret compartment behind screens": 1},         "Camera bank"),
    "Medical Room":       (70,  {"Under medical bed": 1},                        "Healing supplies"),
    "Kitchen/Dining Hall":(60,  {"Under the counter": 1},                        "Food & general supplies"),
    "Workshop":           (90,  {},                                              "Tools; distinct metallic sound"),
    "Storage Room":       (3,   {"Boxes": 7},                                    "General hiding/storage"),
    "Boiler Room":        (20,  {},                                              "Destroy Drives here"),
    "Generator Room":     (20,  {},                                              "Shuts off electricity labyrinth-wide"),
    "Data Centre":        (10,  {},                                              "Insert a Drive to load its data"),
    "Vault":              (100, {},                                              "Holds the Escape Key"),
    "Maintenance Tunnels":(15,  {},                                              "Connective hub"),
    "Hidden Shrine":      (100, {},                                              "Holds the Final Record"),
    "Furnace":            (80,  {},                                              "Destroys Drives"),
    "Dormitory":          (15,  {"Under the bed": 3},                            "Rest"),
    "Courtyard":          (85,  {"Giant tree": 1, "Trees": 5, "Grass": 1},        "Map centre"),
    "Water Reservoir":    (40,  {"Behind water tanks": 1},                       "Holds the water supply"),
    "Armoury":            (30,  {"Under the counter": 1},                        "Unloaded guns - melee only"),
    "Laboratory":         (55,  {"Inside cabinets": 2},                          "Acids/substances"),
    "Hidden Chamber":     (7,   {},                                              "Engine discretion at setup"),
    "Secret Passage":     (7,   {},                                              "Leads to the Hidden Chamber"),
    "Exit Gate":          (100, {},                                              "The escape point"),
}

# Raw adjacency exactly as drawn in the Appendix A map. Edges are made
# bidirectional by build_room_graph() in engine.py.
RAW_CONNECTIONS = {
    "Entrance Hall":       ["Courtyard"],
    "Courtyard":           ["Dormitory", "Library", "Workshop", "Storage Room",
                            "Security Office", "Medical Room", "Entrance Hall"],
    "Dormitory":           ["Kitchen/Dining Hall", "Courtyard", "Library"],
    "Kitchen/Dining Hall": ["Medical Room", "Dormitory"],
    "Medical Room":        ["Security Office", "Kitchen/Dining Hall", "Courtyard"],
    "Library":             ["Archive", "Observatory", "Security Office", "Dormitory", "Courtyard"],
    "Archive":             ["Maintenance Tunnels"],
    "Observatory":         ["Library"],
    "Security Office":     ["Armoury", "Medical Room", "Library", "Exit Gate"],
    "Workshop":            ["Generator Room", "Boiler Room", "Laboratory", "Storage Room", "Courtyard"],
    "Storage Room":        ["Data Centre", "Water Reservoir", "Laboratory",
                            "Maintenance Tunnels", "Workshop", "Courtyard"],
    "Generator Room":      ["Boiler Room", "Data Centre", "Water Reservoir",
                            "Workshop", "Maintenance Tunnels"],
    "Boiler Room":         ["Furnace", "Water Reservoir", "Workshop", "Generator Room"],
    "Water Reservoir":     ["Storage Room", "Generator Room", "Boiler Room"],
    "Data Centre":         ["Generator Room", "Storage Room", "Vault", "Laboratory"],
    "Laboratory":          ["Storage Room", "Workshop", "Data Centre"],
    "Maintenance Tunnels": ["Vault", "Hidden Shrine", "Secret Passage",
                            "Storage Room", "Archive", "Generator Room"],
    "Vault":               ["Exit Gate", "Data Centre", "Maintenance Tunnels"],
    "Secret Passage":      ["Hidden Chamber"],
    "Hidden Chamber":      ["Secret Passage"],
    "Hidden Shrine":       ["Maintenance Tunnels"],
    "Furnace":             ["Boiler Room"],
    "Armoury":             ["Security Office"],
    "Exit Gate":           ["Security Office", "Vault"],
}

# Rooms watched by the Security Office camera bank (3.10), power permitting.
CAMERA_ROOMS = ["Library", "Workshop", "Storage Room", "Medical Room",
                "Observatory", "Dormitory"]

# ---------------------------------------------------------------------------
# APPENDIX E - TRAITS
# number: (visible behaviour, meaning, internal trigger token)
# ---------------------------------------------------------------------------
TRAITS = {
    1:  ("scratches their left ear",              "Seriously considering killing someone",      "considering_kill"),
    2:  ("rubs their hands together",             "Preparing to search/interact with something important", "preparing_search"),
    3:  ("taps their fingers",                    "Thinking through an important decision",     "deciding"),
    4:  ("looks over both shoulders",             "About to lie or hide information",           "about_to_lie"),
    5:  ("adjusts their clothing",                "Preparing for a careful interaction",        "careful_interaction"),
    6:  ("clears their throat",                   "Has carefully thought about what to say",    "prepared_speech"),
    7:  ("looks at the floor",                    "Intentionally withholding information",      "withholding_info"),
    8:  ("checks behind themselves",              "Believes danger may be nearby",              "believes_danger"),
    9:  ("cracks their knuckles",                 "Preparing for physical confrontation",       "preparing_fight"),
    10: ("takes a deep breath",                   "About to make a risky or fast move",         "risky_move"),
    11: ("tilts their head",                      "Analyzing clues or solving a puzzle",        "analyzing_clues"),
    12: ("wipes their hands on their clothing",   "Just handled something important",           "handled_important_item"),
    13: ("stares at the doors",                   "Planning their next movement",               "planning_movement"),
    14: ("freezes briefly",                       "Heard something unexpected",                 "heard_unexpected"),
    15: ("touches their chin",                    "Reasoning through a difficult problem",      "hard_problem"),
    16: ("rubs the back of their neck",           "Feels conflicted or under pressure",         "conflicted"),
    17: ("shifts weight between their feet",      "Uncomfortable with the situation",           "uncomfortable"),
    18: ("checks their pockets",                  "Confirming they still hold an important item","confirm_item"),
    19: ("closes their eyes briefly",             "Has committed to an important decision",     "committed_decision"),
    20: ("hums quietly",                          "Currently feels relatively safe",            "feels_safe"),
    21: ("fidgets with their sleeves",            "Nervous",                                    "nervous"),
    22: ("straightens their posture",             "Preparing to accuse or challenge someone",   "about_to_accuse"),
    23: ("looks toward the ceiling",              "Trying to remember information",             "recalling"),
    24: ("smiles briefly",                        "Believes something went in their favour",    "favorable"),
    25: ("crosses their arms",                    "Evaluating or doubting someone",             "doubting"),
    26: ("rubs their forehead",                   "Confused or overwhelmed",                    "confused"),
    27: ("pauses at the doorway",                 "Checking if it is safe to enter",            "entering_room"),
    28: ("glances at the nearby exits",           "Thinking about escape routes",               "escape_planning"),
    29: ("tightens their grip on what they carry","Feels threatened or expects danger",         "feels_threatened"),
    30: ("looks toward the nearest hiding place", "Deciding whether to hide or attack",         "hide_or_attack"),
}

# Standard 8-player fixed trait distribution (Appendix E).
PLAYER_TRAITS = {
    1: [1, 9, 17, 25],
    2: [2, 10, 18, 26],
    3: [3, 11, 19, 27],
    4: [4, 12, 20, 28],
    5: [5, 13, 21, 29],
    6: [6, 14, 22, 30],
    7: [7, 15, 23],
    8: [8, 16, 24],
}

# ---------------------------------------------------------------------------
# CHAPTER 7 - ROLES  (role name -> (role item, ability summary))
# ---------------------------------------------------------------------------
ROLES = {
    "Investigator":     ("Magnifying Glass", "Richer search results; better at riddles and hidden evidence."),
    "Listener":         ("Hearing Device",   "Sounds come with an exact origin room and distance."),
    "Forensic Analyst": ("Forensic Kit",     "Examining a body reveals cause, rough time and nearby evidence."),
    "Locksmith":        ("Lockpick Set",     "Locks open in half the time and much more quietly."),
    "Scavenger":        ("Utility Backpack", "Better searching, finds compartments, inventory limit 6."),
    "Observer":         ("Binoculars",       "Notices body-language tells others would miss."),
    "Archivist":        ("Notebook",         "Detailed memory; contradictions in others' claims are flagged."),
    "Actor":            ("Disguise Kit",     "May deliberately fake someone else's tell (only role that can)."),
}
ROLE_ITEM_TO_ROLE = {item: role for role, (item, _) in ROLES.items()}

# ---------------------------------------------------------------------------
# CHAPTER 8 - THE EIGHT OBJECTIVES
# ---------------------------------------------------------------------------
OBJECTIVES = {
    1: "Recover Drive A and escape while carrying it (it must be loaded at the Data Centre).",
    2: "Recover Drive B and escape while carrying it (it must be loaded at the Data Centre).",
    3: "Recover Drive C and escape while carrying it (it must be loaded at the Data Centre).",
    4: "Destroy one Drive at the Furnace or Boiler Room before escaping.",
    5: "Find the Final Record and possess it at the moment you escape.",
    6: "Learn another player's secret ID (their role) and escape with that knowledge.",
    7: "Assassinate your assigned target without being correctly identified as the assassin.",
    8: "Solve the labyrinth's final escape mechanism (the Vault chain) before escaping.",
}

# ---------------------------------------------------------------------------
# APPENDIX F - ITEMS
# ---------------------------------------------------------------------------
FLAVOR_ITEMS = {
    "Medical Room":        ["Medical Supplies", "Bandages"],
    "Kitchen/Dining Hall": ["Tinned Food", "Water Bottle"],
    "Workshop":            ["Heavy Wrench", "Crowbar"],
    "Armoury":             ["Unloaded Pistol", "Unloaded Rifle"],
    "Laboratory":          ["Flask of Acid", "Sedative Vial"],
    "Storage Room":        ["Rope", "Torch"],
    "Dormitory":           ["Wool Blanket"],
    "Water Reservoir":     ["Empty Canister"],
    "Hidden Chamber":      ["Old Coin"],
}

IMPROVISED_WEAPONS = {"Heavy Wrench", "Crowbar", "Unloaded Pistol",
                      "Unloaded Rifle", "Flask of Acid"}
HEALING_ITEMS = {"Medical Supplies", "Bandages"}

BASE_INVENTORY_LIMIT = 4
SCAVENGER_INVENTORY_LIMIT = 6

# Clue chain (Appendix D). Each clue is knowledge, not a carried item.
CLUE_LIBRARY = "library_clue"       # found by searching the Library
CLUE_ARCHIVE = "archive_clue"       # found by searching the Archive (needs library clue)
CLUE_MECHANISM = "mechanism_clue"   # found by searching the Hidden Chamber or Vault
