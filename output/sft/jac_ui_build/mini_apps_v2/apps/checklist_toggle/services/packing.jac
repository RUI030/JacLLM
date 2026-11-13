"""Three fixed things to pack and whether each one is packed."""

node PackItem {
    has name: str;
    has packed: bool = False;
}

glob STARTER: list[dict] = [
    {"name": "Passport"},
    {"name": "Charger"},
    {"name": "Toothbrush"}
];

walker:pub open_packing {
    can start with Root entry {
        if not [-->][?:PackItem] {
            for s in STARTER {
                here ++> PackItem(name=s["name"] as str);
            }
        }
        visit [-->][?:PackItem];
    }

    can collect with PackItem entry {
        report here;
    }
}

def:pub set_packed(item_id: str, packed: bool) -> PackItem | None {
    for it in [root-->][?:PackItem] {
        if jid(it) == item_id {
            it.packed = packed;
            return it;
        }
    }
    return None;
}
