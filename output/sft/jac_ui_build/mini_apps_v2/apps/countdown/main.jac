import ".styles.global.css";
import from .components.TeaTimer { TeaTimer }

def:pub app() -> JsxElement {
    return <TeaTimer />;
}
