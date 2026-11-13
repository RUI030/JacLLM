"""One counter value, kept on a single Tally node under root."""

node Tally {
    has value: int = 0;
}

def _tally() -> Tally {
    found = [root-->][?:Tally];
    if found {
        return found[0];
    }
    tally = Tally();
    root ++> tally;
    return tally;
}

def:pub get_count() -> int {
    return _tally().value;
}

def:pub add_one() -> int {
    tally = _tally();
    tally.value = tally.value + 1;
    return tally.value;
}
