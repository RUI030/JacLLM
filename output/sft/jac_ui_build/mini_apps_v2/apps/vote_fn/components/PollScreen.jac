import from .ui.button { Button }
import from .ui.card { Card, CardContent }
sv import from ..services.poll { read_votes, vote }

def:pub PollScreen() -> JsxElement {
    has cats: int = 0;
    has dogs: int = 0;
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = await read_votes();
            cats = result.cats;
            dogs = result.dogs;
        } except Exception as e {
            error = "Could not load the votes.";
        }
        loading = False;
    }

    async def cast(side: str) -> None {
        result = await vote(side);
        cats = result.cats;
        dogs = result.dogs;
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col items-center gap-6 pt-2 pb-2">
                <h1 className="text-2xl font-semibold tracking-tight">{"Cats or dogs?"}</h1>
                <div className="flex gap-3">
                    <Button className="shadow-sm" onClick={lambda -> None { cast("cats"); }}>{"Vote cats"}</Button>
                    <Button className="shadow-sm" onClick={lambda -> None { cast("dogs"); }}>{"Vote dogs"}</Button>
                </div>
                {if loading {
                    <p className="text-sm text-muted-foreground">{"Loading..."}</p>
                } else {
                    <div className="flex flex-col items-center gap-1">
                        <p className="text-2xl font-semibold tabular-nums">{"Cats: " + str(cats)}</p>
                        <p className="text-2xl font-semibold tabular-nums">{"Dogs: " + str(dogs)}</p>
                    </div>
                }}
                {error and <p className="text-sm text-destructive">{error}</p>}
            </CardContent>
        </Card>
    </div>;
}
