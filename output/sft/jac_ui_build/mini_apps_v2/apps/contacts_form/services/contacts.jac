"""Contacts kept under root, in the order they were added."""

node Contact {
    has name: str;
    has email: str;
}

walker:pub list_contacts {
    can start with Root entry {
        visit [-->][?:Contact];
    }

    can gather with Contact entry {
        report here;
    }
}

def:pub add_contact(name: str, email: str) -> Contact {
    contact = Contact(name=name, email=email);
    root ++> contact;
    return contact;
}
