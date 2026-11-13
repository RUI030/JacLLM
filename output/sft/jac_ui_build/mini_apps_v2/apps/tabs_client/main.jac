import ".styles.global.css";
import from .components.HoursPanel { HoursPanel }

def:pub app() -> JsxElement {
    return <HoursPanel />;
}
