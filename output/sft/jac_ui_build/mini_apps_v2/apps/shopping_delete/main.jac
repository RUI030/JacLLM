import from services.shopping { ShopItem, list_shopping, add_item, remove_item }

import ".styles.global.css";
import from .components.ShoppingScreen { ShoppingScreen }

def:pub app() -> JsxElement {
    return <ShoppingScreen />;
}
