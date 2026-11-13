"""Quick notes kept under root, in the order they were written."""

node Jotting {
    has text: str;
}

walker:pub load_notes {
    can begin with Root entry {
        visit [-->][?:Jotting];
    }

    can gather with Jotting entry {
        report here;
    }
}

walker:pub add_note {
    has text: str;

    can create with Root entry {
        jotting = Jotting(text=self.text);
        here ++> jotting;
        report jotting;
    }
}
