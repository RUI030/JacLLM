import from .ui.button { Button }
import from .ui.card { Card, CardContent }

def:pub HoursPanel() -> JsxElement {
    has chosen: str = "Weekdays";

    def hours_text(d: str) -> str {
        if d == "Weekdays" {
            return "Open 9:00 to 18:00";
        } elif d == "Saturday" {
            return "Open 10:00 to 16:00";
        }
        return "Closed";
    }

    def choose_day(d: str) {
        chosen = d;
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col gap-4">
                <h1 className="text-xl font-semibold tracking-tight">{"Opening hours"}</h1>
                <div className="flex gap-2">
                    {for d in ["Weekdays", "Saturday", "Sunday"] {
                        <Button
                            key={d}
                            variant={"default" if d == chosen else "outline"}
                            onClick={lambda -> None { choose_day(d); }}
                        >{d}</Button>
                    }}
                </div>
                <div role="status" aria-label="Hours" className="rounded-lg border bg-background pt-3 pb-3 pl-4 pr-4 text-lg font-medium">{hours_text(chosen)}</div>
            </CardContent>
        </Card>
    </div>;
}
