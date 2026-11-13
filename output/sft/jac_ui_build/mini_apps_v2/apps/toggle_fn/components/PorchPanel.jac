import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.lamp { read_lamp, flip_lamp }

def:pub PorchPanel() -> JsxElement {
    has lit: bool = False;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            value = await read_lamp();
            lit = value;
        } except Exception as e {
            error = "Could not load the light.";
        }
        loading = False;
    }

    async def handle_flip() -> None {
        value = await flip_lamp();
        lit = value;
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col items-center gap-6 pt-2 pb-2">
                <h1 className="text-2xl font-semibold tracking-tight">{"Porch light"}</h1>
                {if loading {
                    <p className="text-sm text-muted-foreground">{"Loading..."}</p>
                } else {
                    <p className="text-xl font-semibold">{"The light is on" if lit else "The light is off"}</p>
                }}
                {error and <p className="text-sm text-destructive">{error}</p>}
                <Button className="shadow-sm" onClick={lambda -> None { handle_flip(); }}>
                    {"Turn off" if lit else "Turn on"}
                </Button>
            </CardContent>
        </Card>
    </div>;
}
