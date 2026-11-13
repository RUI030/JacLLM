import ".styles.global.css";
import from .components.Calculator { Calculator }

def:pub app() -> JsxElement {
    return <Calculator />;
}
