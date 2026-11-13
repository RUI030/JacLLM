import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.card { Card, CardContent }

def:pub TipScreen() -> JsxElement {
    has bill: str = "";
    has tip: float = 0.0;
    has total: float = 0.0;
    has invalid: bool = False;

    def money(n: float) -> str {
        cents = round(n * 100);
        dollars = int(cents / 100);
        rest = int(cents - dollars * 100);
        if rest < 10 {
            return "$" + str(dollars) + ".0" + str(rest);
        }
        return "$" + str(dollars) + "." + str(rest);
    }

    def handle_bill(e: ChangeEvent) { bill = e.target.value; }

    def apply_percent(p: int) {
        text = bill.strip();
        if text == "" {
            invalid = True;
            return;
        }
        amount = float(text);
        if amount != amount {
            invalid = True;
            return;
        }
        invalid = False;
        tip = amount * p / 100;
        total = amount + amount * p / 100;
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardContent className="flex flex-col gap-4">
                <h1 className="text-xl font-semibold tracking-tight">{"Tip calculator"}</h1>
                <div className="flex flex-col gap-2">
                    <label htmlFor="bill" className="text-sm font-medium">{"Bill"}</label>
                    <Input id="bill" value={bill} onChange={handle_bill} placeholder="0.00" />
                </div>
                <div className="grid grid-cols-3 gap-2">
                    {for p in [10, 15, 20] {
                        <Button
                            key={p}
                            variant={"outline"}
                            onClick={lambda -> None { apply_percent(p); }}
                        >{str(p) + "%"}</Button>
                    }}
                </div>
                {if invalid {
                    <p role="status" className="text-sm text-destructive">{"Enter a bill amount"}</p>
                } else {
                    <div role="status" className="flex flex-col gap-1 text-lg font-semibold tabular-nums">
                        <p>{"Tip: " + money(tip)}</p>
                        <p>{"Total: " + money(total)}</p>
                    </div>
                }}
            </CardContent>
        </Card>
    </div>;
}
