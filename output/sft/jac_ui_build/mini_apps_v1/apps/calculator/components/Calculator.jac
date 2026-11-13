import from .ui.button { Button }
import from .ui.card { Card, CardContent }

def:pub Calculator() -> JsxElement {
    has display: str = "0";
    has value: float = 0.0;
    has stored: float = 0.0;
    has op: str = "";
    has fresh: bool = True;

    def compute(a: float, b: float, o: str) -> float {
        if o == "+" {
            return a + b;
        } elif o == "-" {
            return a - b;
        } elif o == "×" {
            return a * b;
        }
        return a / b;
    }

    def show(n: float) -> str {
        if n == round(n) {
            return str(round(n));
        }
        return str(round(n, 2));
    }

    def clear() {
        display = "0";
        value = 0.0;
        stored = 0.0;
        op = "";
        fresh = True;
    }

    def press_digit(d: str) {
        if fresh or display == "0" or display == "Error" {
            display = d;
            value = int(d);
        } else {
            display = display + d;
            value = value * 10 + int(d);
        }
        fresh = False;
    }

    def press_op(o: str) {
        if display == "Error" {
            return;
        }
        if op != "" and not fresh {
            if op == "÷" and value == 0 {
                clear();
                display = "Error";
                return;
            }
            result = compute(stored, value, op);
            stored = result;
            value = result;
            display = show(result);
        } else {
            stored = value;
        }
        op = o;
        fresh = True;
    }

    def press_equals() {
        if op == "" or display == "Error" {
            return;
        }
        if op == "÷" and value == 0 {
            clear();
            display = "Error";
            return;
        }
        result = compute(stored, value, op);
        value = result;
        stored = 0.0;
        display = show(result);
        op = "";
        fresh = True;
    }

    def press(k: str) {
        if k == "C" {
            clear();
        } elif k == "=" {
            press_equals();
        } elif k in ["+", "-", "×", "÷"] {
            press_op(k);
        } else {
            press_digit(k);
        }
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-xs shadow-sm">
            <CardContent className="flex flex-col gap-4">
                <h1 className="text-xl font-semibold tracking-tight">{"Calculator"}</h1>
                <div role="status" aria-label="Display" className="rounded-lg border bg-background pt-3 pb-3 pl-4 pr-4 text-right text-3xl font-semibold tabular-nums">{display}</div>
                <div className="grid grid-cols-4 gap-2">
                    {for k in ["7", "8", "9", "÷", "4", "5", "6", "×", "1", "2", "3", "-", "C", "0", "=", "+"] {
                        <Button
                            key={k}
                            variant={"outline" if k in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"] else "default"}
                            className="h-12 text-lg"
                            onClick={lambda -> None { press(k); }}
                        >{k}</Button>
                    }}
                </div>
            </CardContent>
        </Card>
    </div>;
}
