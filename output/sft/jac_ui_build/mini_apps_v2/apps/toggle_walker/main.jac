import from services.mute { MuteFlag, read_mute, flip_mute }

import ".styles.global.css";
import from .components.QuietPanel { QuietPanel }

def:pub app() -> JsxElement {
    return <QuietPanel />;
}
