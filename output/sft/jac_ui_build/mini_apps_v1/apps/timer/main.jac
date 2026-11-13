import ".styles.global.css";
import from .components.Stopwatch { Stopwatch }

def:pub app() -> JsxElement {
    return <Stopwatch />;
}
