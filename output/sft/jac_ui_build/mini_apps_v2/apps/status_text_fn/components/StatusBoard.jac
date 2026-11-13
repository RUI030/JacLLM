import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.card { Card, CardContent }
sv import from ..services.status { read_status, save_status }

def:pub StatusBoard() -> JsxElement {
    has current: str = "";
    has draft: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            value = await read_status();
            current = value;
        } except Exception {
            error = "Could not load the status.";
        }
        loading = False;
    }

    def handle_draft(e: ChangeEvent) { draft = e.target.value; }

    async def store_status(text: str) -> None {
        value = await save_status(text);
        current = value;
    }

    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not draft.strip() {
            return;
        }
        store_status(draft.strip());
        draft = "";
    }

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-xl flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Team status"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-6">
                    <form onSubmit={handle_submit} className="flex items-end gap-3">
                        <div className="flex flex-1 flex-col gap-2">
                            <label htmlFor="status" className="text-sm font-medium">{"Status"}</label>
                            <Input id="status" value={draft} onChange={handle_draft} placeholder="What is the team up to?" />
                        </div>
                        <Button type="submit">{"Save"}</Button>
                    </form>
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading status..."}</p>
                    } elif current == "" {
                        <p className="text-sm text-muted-foreground">{"No status yet"}</p>
                    } else {
                        <p className="text-base font-medium">{"Current status: " + current}</p>
                    }}
                </CardContent>
            </Card>
        </main>
    </div>;
}
