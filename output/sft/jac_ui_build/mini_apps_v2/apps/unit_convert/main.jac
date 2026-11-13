import ".styles.global.css";
import from .components.KmPanel { KmPanel }

def:pub app() -> JsxElement {
    return <KmPanel />;
}
