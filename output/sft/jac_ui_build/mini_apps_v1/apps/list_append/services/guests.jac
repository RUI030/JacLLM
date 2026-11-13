"""Guests on the list, in the order they were added."""

node Guest {
    has name: str;
}

walker:pub open_guests {
    can start with Root entry {
        visit [-->][?:Guest];
    }

    can collect with Guest entry {
        report here;
    }
}

def:pub add_guest(name: str) -> Guest {
    guest = Guest(name=name);
    root ++> guest;
    return guest;
}
