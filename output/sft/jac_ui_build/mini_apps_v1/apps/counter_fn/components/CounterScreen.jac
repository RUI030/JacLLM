import from "@hugeicons/react" { HugeiconsIcon }
import from "@hugeicons/core-free-icons" { PlusSignIcon }
import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.counter { get_count, add_one }

def:pub CounterScreen() -> JsxElement {
    has count: int = 0;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            value = await get_count();
            count = value;
        } except Exception as e {
            error = "Could not load the count.";
        }
        loading = False;
    }

    async def handle_add() -> None {
        value = await add_one();
        count = value;
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col items-center gap-6 pt-2 pb-2">
                <h1 className="text-2xl font-semibold tracking-tight">{"Counter"}</h1>
                {if loading {
                    <p className="text-sm text-muted-foreground">{"Loading..."}</p>
                } else {
                    <p className="text-4xl font-semibold tabular-nums">{"Count: " + str(count)}</p>
                }}
                {error and <p className="text-sm text-destructive">{error}</p>}
                <Button className="shadow-sm" onClick={lambda -> None { handle_add(); }}>
                    <HugeiconsIcon icon={PlusSignIcon} strokeWidth={2} />{"Add one"}
                </Button>
            </CardContent>
        </Card>
    </div>;
}
