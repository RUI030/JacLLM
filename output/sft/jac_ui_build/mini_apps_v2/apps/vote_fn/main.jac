import from services.poll { read_votes, vote, Ballot }

import ".styles.global.css";
import from .components.PollScreen { PollScreen }

def:pub app() -> JsxElement {
    return <PollScreen />;
}
