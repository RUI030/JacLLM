import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.card { Card, CardContent }
sv import from ..services.jottings { Jotting, load_notes, add_note }

def:pub NotesBoard() -> JsxElement {
    has notes: list[Jotting] = [];
    has draft: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn load_notes();
            notes = result.reports or [];
        } except Exception {
            error = "Could not load the notes.";
        }
        loading = False;
    }

    def handle_draft(e: ChangeEvent) { draft = e.target.value; }

    async def save_note(value: str) -> None {
        try {
            result = root spawn add_note(text=value);
            if len(result.reports) > 0 {
                notes = notes + [result.reports[0]];
            }
            error = "";
        } except Exception {
            error = "Could not save the note.";
        }
    }

    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not draft.strip() {
            return;
        }
        save_note(draft.strip());
        draft = "";
    }

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-lg flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Quick notes"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-6">
                    <form onSubmit={handle_submit} className="flex items-end gap-3">
                        <div className="flex flex-1 flex-col gap-2">
                            <label htmlFor="note" className="text-sm font-medium">{"Note"}</label>
                            <Input id="note" value={draft} onChange={handle_draft} placeholder="What do you want to remember?" />
                        </div>
                        <Button type="submit">{"Add note"}</Button>
                    </form>
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading notes..."}</p>
                    } elif len(notes) == 0 {
                        <p className="rounded-xl border border-dashed pt-8 pb-8 text-center text-sm text-muted-foreground">{"Nothing written yet"}</p>
                    } else {
                        <ul className="flex flex-col gap-2">
                            {for n in notes {
                                <li key={jid(n)} className="rounded-lg border bg-background pt-3 pb-3 pl-4 pr-4 text-sm">{n.text}</li>
                            }}
                        </ul>
                    }}
                </CardContent>
            </Card>
        </main>
    </div>;
}
