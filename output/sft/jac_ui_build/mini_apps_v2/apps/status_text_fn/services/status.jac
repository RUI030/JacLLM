"""The team status text, kept on a single StatusNote node under root."""

node StatusNote {
    has text: str = "";
}

def _note() -> StatusNote {
    found = [root-->][?:StatusNote];
    if found {
        return found[0];
    }
    note = StatusNote();
    root ++> note;
    return note;
}

def:pub read_status() -> str {
    return _note().text;
}

def:pub save_status(text: str) -> str {
    note = _note();
    if text.strip() {
        note.text = text.strip();
    }
    return note.text;
}
