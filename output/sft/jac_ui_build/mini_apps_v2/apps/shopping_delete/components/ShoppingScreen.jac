import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.field { Field, FieldLabel }
import from .ui.empty { Empty, EmptyHeader, EmptyTitle }
import from .ui.card { Card, CardContent }
sv import from ..services.shopping { ShopItem, list_shopping, add_item, remove_item }

def:pub ShoppingScreen() -> JsxElement {
    has items: list[ShopItem] = [];
    has draft: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn list_shopping();
            items = result.reports or [];
        } except Exception {
            error = "Could not load the shopping list.";
        }
        loading = False;
    }

    def handle_draft(e: ChangeEvent) { draft = e.target.value; }

    async def save_item(value: str) -> None {
        created = await add_item(value);
        items = items + [created];
    }

    async def drop_item(item: ShopItem) -> None {
        removed = await remove_item(jid(item));
        if removed {
            items = [i for i in items if jid(i) != jid(item)];
        }
    }

    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not draft.strip() {
            return;
        }
        save_item(draft.strip());
        draft = "";
    }

    return <div className="min-h-svh bg-muted/40">
        <main className="mx-auto flex w-full max-w-lg flex-col gap-6 pt-10 pb-12 pl-6 pr-6">
            <h1 className="text-2xl font-semibold tracking-tight">{"Shopping list"}</h1>
            <Card className="shadow-sm">
                <CardContent className="flex flex-col gap-6">
                    <form onSubmit={handle_submit} className="flex items-end gap-3">
                        <Field className="flex-1">
                            <FieldLabel htmlFor="item">{"Item"}</FieldLabel>
                            <Input id="item" value={draft} onChange={handle_draft} placeholder="What do you need?" />
                        </Field>
                        <Button type="submit">{"Add item"}</Button>
                    </form>
                    {error and <p className="text-sm text-destructive">{error}</p>}
                    {if loading {
                        <p className="text-sm text-muted-foreground">{"Loading items..."}</p>
                    } elif len(items) == 0 {
                        <div className="rounded-xl border border-dashed pt-8 pb-8">
                            <Empty>
                                <EmptyHeader>
                                    <EmptyTitle>{"The list is empty"}</EmptyTitle>
                                </EmptyHeader>
                            </Empty>
                        </div>
                    } else {
                        <ul className="flex flex-col divide-y rounded-lg border">
                            {for it in items {
                                <li key={jid(it)} className="flex items-center justify-between gap-3 pt-2 pb-2 pl-4 pr-2">
                                    <span className="font-medium">{it.name}</span>
                                    <Button
                                        variant="outline"
                                        aria-label={"Remove " + it.name}
                                        onClick={lambda -> None { drop_item(it); }}
                                    >{"Remove"}</Button>
                                </li>
                            }}
                        </ul>
                    }}
                </CardContent>
            </Card>
        </main>
    </div>;
}
