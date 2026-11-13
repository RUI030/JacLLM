import from services.room { RoomDial, open_room, warm_up, cool_down, reset_room }

import ".styles.global.css";
import from .components.RoomPanel { RoomPanel }

def:pub app() -> JsxElement {
    return <RoomPanel />;
}
