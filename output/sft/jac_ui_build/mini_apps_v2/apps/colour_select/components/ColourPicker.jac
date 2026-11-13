import from .ui.button { Button }
import from .ui.card { Card, CardContent }
import from .ui.field { Field, FieldLabel }
import from .ui.select { Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem }
sv import from ..services.badge { BadgeColour, open_colour, save_colour }

def:pub ColourPicker() -> JsxElement {
    has chosen: str = "";
    has saved: str = "";
    has loading: bool = True;
    has error: str = "";

    async can with entry {
        try {
            result = root spawn open_colour();
            if len(result.reports) > 0 {
                saved = result.reports[0].shade as str;
            }
        } except Exception as e {
            error = "Could not load the saved colour.";
        }
        loading = False;
    }

    def handle_choice(value: str) { chosen = value; }

    async def handle_save() -> None {
        if not chosen {
            return;
        }
        try {
            result = root spawn save_colour(colour=chosen);
            if len(result.reports) > 0 {
                saved = result.reports[0].shade as str;
            }
            error = "";
        } except Exception as e {
            error = "Could not save the colour.";
        }
    }

    shown = saved if saved else "none";
    status = "Saved colour: " + shown;

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-500">
            <CardContent className="flex flex-col gap-5 pt-2 pb-2">
                <h1 className="text-2xl font-semibold tracking-tight">{"Badge colour"}</h1>
                <Field>
                    <FieldLabel htmlFor="colour">{"Colour"}</FieldLabel>
                    <Select value={chosen} onValueChange={handle_choice}>
                        <SelectTrigger id="colour" className="w-full"><SelectValue /></SelectTrigger>
                        <SelectContent><SelectGroup>
                            {for c in ["Red", "Green", "Blue"] {
                                <SelectItem key={c} value={c}>{c}</SelectItem>
                            }}
                        </SelectGroup></SelectContent>
                    </Select>
                </Field>
                <Button className="w-full shadow-sm" onClick={lambda -> None { handle_save(); }}>{"Save colour"}</Button>
                <p className="text-sm text-muted-foreground">{"Loading..." if loading else status}</p>
                {error and <p className="text-sm text-destructive">{error}</p>}
            </CardContent>
        </Card>
    </div>;
}
