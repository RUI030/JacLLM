import from services.guests { Guest, open_guests, add_guest }

import ".styles.global.css";
import from .components.GuestList { GuestList }

def:pub app() -> JsxElement {
    return <GuestList />;
}
