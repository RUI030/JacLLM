import from .ui.button { Button }
import from .ui.card { Card, CardContent }
import from .ui.input { Input }

def:pub KmPanel() -> JsxElement {
    has text: str = "";
    has line: str = "Enter a distance";

    def show(n: float) -> str {
        if n == round(n) {
            return str(round(n));
        }
        return str(round(n, 2));
    }

    def describe(raw: str) -> str {
        try {
            km = float(raw.strip());
            return show(km) + " km is " + show(km * 0.621371) + " miles";
        } except Exception {
            return "That is not a number";
        }
    }

    def handle_text(e: ChangeEvent) { text = e.target.value; }

    def convert() {
        line = describe(text);
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col gap-4">
                <h1 className="text-xl font-semibold tracking-tight">{"Kilometres to miles"}</h1>
                <div className="flex flex-col gap-2">
                    <label htmlFor="km" className="text-sm font-medium">{"Kilometres"}</label>
                    <Input id="km" value={text} onChange={handle_text} placeholder="0" />
                </div>
                <Button onClick={lambda -> None { convert(); }}>{"Convert"}</Button>
                <p role="status" className="text-lg font-semibold tabular-nums">{line}</p>
            </CardContent>
        </Card>
    </div>;
}
