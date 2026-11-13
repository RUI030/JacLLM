import from services.scores { Team, open_scoreboard, add_point, reset_scores }

import ".styles.global.css";
import from .components.ScoreboardPanel { ScoreboardPanel }

def:pub app() -> JsxElement {
    return <ScoreboardPanel />;
}
