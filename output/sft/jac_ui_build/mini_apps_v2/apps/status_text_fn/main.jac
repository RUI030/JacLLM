import from services.status { read_status, save_status }

import ".styles.global.css";
import from .components.StatusBoard { StatusBoard }

def:pub app() -> JsxElement {
    return <StatusBoard />;
}
