import from services.badge { BadgeColour, open_colour, save_colour }

import ".styles.global.css";
import from .components.ColourPicker { ColourPicker }

def:pub app() -> JsxElement {
    return <ColourPicker />;
}
