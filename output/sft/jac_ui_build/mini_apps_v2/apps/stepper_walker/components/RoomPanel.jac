import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.room { RoomDial, open_room, warm_up, cool_down, reset_room }

def:pub RoomPanel() -> JsxElement {
    has degrees: int = 20;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_room();
            if len(result.reports) > 0 {
                degrees = result.reports[0].degrees as int;
            }
        } except Exception as e {
            error = "Could not load the temperature.";
        }
        loading = False;
    }

    async def handle_warmer() -> None {
        try {
            result = root spawn warm_up();
            if len(result.reports) > 0 {
                degrees = result.reports[0].degrees as int;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the temperature.";
        }
    }

    async def handle_cooler() -> None {
        try {
            result = root spawn cool_down();
            if len(result.reports) > 0 {
                degrees = result.reports[0].degrees as int;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the temperature.";
        }
    }

    async def handle_reset() -> None {
        try {
            result = root spawn reset_room();
            if len(result.reports) > 0 {
                degrees = result.reports[0].degrees as int;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the temperature.";
        }
    }

    label = str(degrees) + " °C";

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col items-center gap-5 pt-2 pb-2 text-center">
                <h1 className="text-2xl font-semibold tracking-tight">{"Room temperature"}</h1>
                <span className="text-4xl font-semibold tracking-tight tabular-nums">{"Loading..." if loading else label}</span>
                {error and <p className="text-sm text-destructive">{error}</p>}
                <div className="flex w-full gap-2">
                    <Button className="flex-1 shadow-sm" onClick={lambda -> None { handle_warmer(); }}>{"Warmer"}</Button>
                    <Button className="flex-1 shadow-sm" variant="outline" onClick={lambda -> None { handle_cooler(); }}>{"Cooler"}</Button>
                </div>
                <Button className="w-full" variant="outline" onClick={lambda -> None { handle_reset(); }}>{"Reset"}</Button>
            </CardContent>
        </Card>
    </div>;
}
