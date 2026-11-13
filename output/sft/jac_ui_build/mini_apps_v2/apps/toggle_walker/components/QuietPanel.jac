import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.mute { MuteFlag, read_mute, flip_mute }

def:pub QuietPanel() -> JsxElement {
    has muted: bool = False;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn read_mute();
            if len(result.reports) > 0 {
                muted = result.reports[0].muted as bool;
            }
        } except Exception as e {
            error = "Could not load the setting.";
        }
        loading = False;
    }

    async def handle_flip() -> None {
        try {
            result = root spawn flip_mute();
            if len(result.reports) > 0 {
                muted = result.reports[0].muted as bool;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the setting.";
        }
    }

    status = "Notifications are muted" if muted else "Notifications are on";
    action = "Unmute" if muted else "Mute";

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col items-center gap-5 pt-2 pb-2 text-center">
                <h1 className="text-2xl font-semibold tracking-tight">{"Do not disturb"}</h1>
                <span className="text-lg">{"Loading..." if loading else status}</span>
                {error and <p className="text-sm text-destructive">{error}</p>}
                <Button className="w-full shadow-sm" onClick={lambda -> None { handle_flip(); }}>{action}</Button>
            </CardContent>
        </Card>
    </div>;
}
