import from .a { a_value }

enum Status { READY = "ready", DONE = "done" }

def b_value() -> str {
    return "b";
}

def b_label() -> str {
    return b_value();
}
