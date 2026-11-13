import from services.jottings { Jotting, load_notes, add_note }

import ".styles.global.css";
import from .components.NotesBoard { NotesBoard }

def:pub app() -> JsxElement {
    return <NotesBoard />;
}
