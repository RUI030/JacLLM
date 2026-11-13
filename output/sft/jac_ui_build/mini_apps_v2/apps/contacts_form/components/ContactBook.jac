import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.table { Table, TableHeader, TableBody, TableRow, TableHead, TableCell }
import from .ui.card { Card, CardContent }
sv import from ..services.contacts { Contact, list_contacts, add_contact }

def:pub ContactBook() -> JsxElement {
    has contacts: list[Contact] = [];
    has name: str = "";
    has email: str = "";
    has missing: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn list_contacts();
            contacts = result.reports or [];
        } except Exception {
            error = "Could not load the contacts.";
        }
        loading = False;
    }

    def handle_name(e: ChangeEvent) { name = e.target.value; }

    def handle_email(e: ChangeEvent) { email = e.target.value; }

    async def save_contact(who: str, address: str) -> None {
        created = await add_contact(who, address);
        contacts = contacts + [created];
    }

    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not name.strip() or not email.strip() {
            missing = "Name and email are both needed";
            return;
        }
        save_contact(name.strip(), email.strip());
        missing = "";
        name = "";
        email = "";
    }

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Contacts"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-6">
                    <form onSubmit={handle_submit} className="flex flex-col gap-4">
                        <div className="flex flex-col gap-2">
                            <label htmlFor="contact-name" className="text-sm font-medium">{"Name"}</label>
                            <Input id="contact-name" value={name} onChange={handle_name} placeholder="Full name" />
                        </div>
                        <div className="flex flex-col gap-2">
                            <label htmlFor="contact-email" className="text-sm font-medium">{"Email"}</label>
                            <Input id="contact-email" value={email} onChange={handle_email} placeholder="name@example.com" />
                        </div>
                        {missing and <p className="text-sm text-destructive">{missing}</p>}
                        <Button type="submit" className="self-start">{"Add contact"}</Button>
                    </form>
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading contacts..."}</p>
                    } elif len(contacts) == 0 {
                        <p className="rounded-xl border border-dashed pt-8 pb-8 text-center text-sm text-muted-foreground">{"No contacts yet"}</p>
                    } else {
                        <div className="overflow-hidden rounded-lg border">
                            <Table>
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="text-muted-foreground">{"Name"}</TableHead>
                                        <TableHead className="text-muted-foreground">{"Email"}</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {for c in contacts {
                                        <TableRow key={jid(c)}>
                                            <TableCell className="font-medium">{c.name}</TableCell>
                                            <TableCell className="text-muted-foreground">{c.email}</TableCell>
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
