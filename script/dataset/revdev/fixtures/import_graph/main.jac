import from .a { a_value }
import from .missing { Ghost }

with entry {
    print(a_value());
}
