import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.scores { Team, open_scoreboard, add_point, reset_scores }

def:pub ScoreboardPanel() -> JsxElement {
    has teams: list[Team] = [];
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_scoreboard();
            teams = result.reports or [];
        } except Exception as e {
            error = "Could not load the scores.";
        }
        loading = False;
    }

    async def score_for(team_name: str) -> None {
        try {
            result = root spawn add_point(team=team_name);
            if len(result.reports) > 0 {
                updated = result.reports[0];
                teams = [updated if jid(t) == jid(updated) else t for t in teams];
            }
            error = "";
        } except Exception as e {
            error = "Could not save the point.";
        }
    }

    async def start_new_game() -> None {
        try {
            result = root spawn reset_scores();
            teams = result.reports or [];
            error = "";
        } except Exception as e {
            error = "Could not reset the scores.";
        }
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-md shadow-sm">
            <CardContent className="flex flex-col gap-6 pt-2 pb-2">
                <h1 className="text-center text-2xl font-semibold tracking-tight">{"Scoreboard"}</h1>
                {if loading {
                    <p className="text-center text-sm text-muted-foreground">{"Loading..."}</p>
                } else {
                    <div className="grid grid-cols-2 gap-4">
                        {for t in teams {
                            <div key={jid(t)} className="flex flex-col items-center gap-3 rounded-lg border pt-4 pb-4 pl-4 pr-4">
                                <span className="text-3xl font-semibold tracking-tight tabular-nums">{t.name + ": " + str(t.score)}</span>
                                <Button className="w-full" onClick={lambda -> None { score_for(t.name); }}>{t.name + " scores"}</Button>
                            </div>
                        }}
                    </div>
                }}
                {error and <p className="text-center text-sm text-destructive">{error}</p>}
                <Button variant="outline" className="w-full" onClick={lambda -> None { start_new_game(); }}>{"New game"}</Button>
            </CardContent>
        </Card>
    </div>;
}
