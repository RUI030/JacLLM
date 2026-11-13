import from services.packing { PackItem, open_packing, set_packed }

import ".styles.global.css";
import from .components.PackingList { PackingList }

def:pub app() -> JsxElement {
    return <PackingList />;
}
