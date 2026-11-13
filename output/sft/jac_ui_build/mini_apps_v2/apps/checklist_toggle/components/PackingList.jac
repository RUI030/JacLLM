import from .ui.checkbox { Checkbox }
import from .ui.card { Card, CardContent }
sv import from ..services.packing { PackItem, open_packing, set_packed }

def:pub PackingList() -> JsxElement {
    has items: list[PackItem] = [];
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_packing();
            items = result.reports;
        } except Exception as e {
            error = "Could not load the packing list.";
        }
        loading = False;
    }

    async def handle_packed(item: PackItem) -> None {
        updated = await set_packed(jid(item), not item.packed);
        if updated {
            items = [updated if jid(i) == jid(item) else i for i in items];
        }
    }

    packed_count = len([i for i in items if i.packed]);
    summary = str(packed_count) + " of " + str(len(items)) + " packed";

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-md flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Packing list"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-4">
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading..."}</p>
                    } else {
                        <ul className="flex flex-col divide-y rounded-lg border">
                            {for item in items {
                                <li key={jid(item)} className="flex items-center gap-3 pt-3 pb-3 pl-4 pr-4">
                                    <Checkbox
                                        aria-label={item.name}
                                        checked={item.packed}
                                        onCheckedChange={lambda -> None { handle_packed(item); }}
                                    />
                                    <span className={"text-sm font-medium " + ("text-muted-foreground line-through" if item.packed else "")}>{item.name}</span>
                                </li>
                            }}
                        </ul>
                    }}
                    {if not loading {
                        <p className="text-sm tabular-nums text-muted-foreground">{summary}</p>
                    }}
                </CardContent>
            </Card>
        </main>
    </div>;
}
