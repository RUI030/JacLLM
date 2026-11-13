import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.table { Table, TableHeader, TableBody, TableRow, TableHead, TableCell }
import from .ui.card { Card, CardContent }
sv import from ..services.guests { Guest, open_guests, add_guest }

def:pub GuestList() -> JsxElement {
    has guests: list[Guest] = [];
    has name: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_guests();
            guests = result.reports or [];
        } except Exception {
            error = "Could not load the guest list.";
        }
        loading = False;
    }

    def handle_name(e: ChangeEvent) { name = e.target.value; }

    async def save_guest(value: str) -> None {
        created = await add_guest(value);
        guests = guests + [created];
    }

    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not name.strip() {
            return;
        }
        save_guest(name.strip());
        name = "";
    }

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-xl flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Guest list"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-6">
                    <form onSubmit={handle_submit} className="flex items-end gap-3">
                        <div className="flex flex-1 flex-col gap-2">
                            <label htmlFor="name" className="text-sm font-medium">{"Name"}</label>
                            <Input id="name" value={name} onChange={handle_name} placeholder="Who is coming?" />
                        </div>
                        <Button type="submit">{"Add guest"}</Button>
                    </form>
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading guests..."}</p>
                    } elif len(guests) == 0 {
                        <p className="rounded-xl border border-dashed pt-8 pb-8 text-center text-sm text-muted-foreground">{"No guests yet"}</p>
                    } else {
                        <div className="overflow-hidden rounded-lg border">
                            <Table>
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="w-12 text-muted-foreground">{"#"}</TableHead>
                                        <TableHead className="text-muted-foreground">{"Name"}</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {for (i, g) in enumerate(guests) {
                                        <TableRow key={jid(g)}>
                                            <TableCell className="tabular-nums text-muted-foreground">{str(i + 1)}</TableCell>
                                            <TableCell className="font-medium">{g.name}</TableCell>
                                        </TableRow>
                                    }}
                                </TableBody>
                            </Table>
                        </div>
                    }}
                </CardContent>
            </Card>
        </main>
    </div>;
}
