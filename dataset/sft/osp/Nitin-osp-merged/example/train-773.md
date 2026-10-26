# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "osp",
  "fp": "osp_A_09__mm3_v54",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp_A_09__mm3_v54",
  "tier": "legacy_test_verified",
  "verification": "check+tests",
  "n_tokens": 414,
  "n_answer_tokens": 339
}
```

## USER

I'm making a tiny dungeon crawler in Jac. Rooms are chained nodes and one special room holds the treasure. A hunter walker should check rooms one by one while counting how many it has seen, and terminate the entire search immediately when it finds the treasure room — rooms past the vault must never be visited.

## ASSISTANT

"""Dungeon crawler: chained room nodes with a treasure vault; a Hunter walker counts rooms and stops the moment it finds the treasure."""

node Room {
    has name: str = "";
    has is_treasure: bool = False;
}

walker Hunter {
    has rooms_checked: int = 0;

    can start with Root entry {
        print("Hunter enters the dungeon...");
        visit [-->] else { disengage; }
    }

    can explore with Room entry {
        self.rooms_checked += 1;
        if here.is_treasure {
            print(f"Found the treasure in '{here.name}' after checking {self.rooms_checked} room(s). Hunt ends.");
            disengage;
        }
        print(f"Checked '{here.name}' — no treasure here. ({self.rooms_checked} checked)");
        visit [-->] else { disengage; }
    }
}

with entry {
    entry_room = Room(name="Dusty Antechamber");
    armory = Room(name="Rusty Armory");
    library = Room(name="Forbidden Library");
    vault = Room(name="Sealed Vault", is_treasure=True);
    forbidden_halls = Room(name="Forbidden Halls Beyond");
    inner_sanctum = Room(name="Inner Sanctum");

    root ++> entry_room
        ++> armory
        ++> library
        ++> vault
        ++> forbidden_halls
        ++> inner_sanctum;

    root spawn Hunter();
}
