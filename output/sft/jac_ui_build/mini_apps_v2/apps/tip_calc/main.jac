import ".styles.global.css";
import from .components.TipScreen { TipScreen }

def:pub app() -> JsxElement {
    return <TipScreen />;
}
