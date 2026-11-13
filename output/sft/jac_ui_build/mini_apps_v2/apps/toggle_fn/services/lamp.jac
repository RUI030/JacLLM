"""The porch light switch, kept on a single Lamp node under root."""

node Lamp {
    has lit: bool = False;
}

def _lamp() -> Lamp {
    found = [root-->][?:Lamp];
    if found {
        return found[0];
    }
    lamp = Lamp();
    root ++> lamp;
    return lamp;
}

def:pub read_lamp() -> bool {
    return _lamp().lit;
}

def:pub flip_lamp() -> bool {
    lamp = _lamp();
    lamp.lit = not lamp.lit;
    return lamp.lit;
}
