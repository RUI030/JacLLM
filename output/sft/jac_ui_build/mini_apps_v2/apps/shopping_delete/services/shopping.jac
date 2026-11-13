"""Items on the shopping list, in the order they were added."""

node ShopItem {
    has name: str;
}

walker:pub list_shopping {
    can start with Root entry {
        visit [-->][?:ShopItem];
    }

    can gather with ShopItem entry {
        report here;
    }
}

def:pub add_item(name: str) -> ShopItem {
    entry_node = ShopItem(name=name);
    root ++> entry_node;
    return entry_node;
}

def:pub remove_item(item_id: str) -> bool {
    for it in [root-->][?:ShopItem] {
        if jid(it) == item_id {
            del it;
            return True;
        }
    }
    return False;
}
