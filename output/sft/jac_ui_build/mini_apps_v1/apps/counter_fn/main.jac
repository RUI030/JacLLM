import from services.counter { get_count, add_one }

import ".styles.global.css";
import from .components.CounterScreen { CounterScreen }

def:pub app() -> JsxElement {
    return <CounterScreen />;
}
