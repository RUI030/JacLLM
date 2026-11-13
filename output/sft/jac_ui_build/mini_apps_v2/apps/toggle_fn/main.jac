import from services.lamp { read_lamp, flip_lamp }

import ".styles.global.css";
import from .components.PorchPanel { PorchPanel }

def:pub app() -> JsxElement {
    return <PorchPanel />;
}
