import from .ui.button { Button }
import from .ui.card { Card, CardHeader, CardTitle, CardDescription, CardContent }
import from .Ticker { Ticker }

glob _left: int = 180;

def drop_second() -> int {
    if _left > 0 {
        _left = _left - 1;
    }
    return _left;
}

def refill() -> int {
    _left = 180;
    return _left;
}

def clock_text(total: int) -> str {
    secs = total % 60;
    mins = (total - secs) / 60;
    return str(mins) + ":" + str(secs).zfill(2);
}

def:pub TeaTimer() -> JsxElement {
    has seconds: int = 180;
    has running: bool = False;
    has finished: bool = False;

    def handle_tick() {
        left = drop_second();
        seconds = left;
        if left == 0 {
            running = False;
            finished = True;
        }
    }
    def handle_start(e: MouseEvent) {
        if not running {
            seconds = refill();
            finished = False;
            running = True;
        }
    }
    def handle_reset(e: MouseEvent) {
        running = False;
        finished = False;
        seconds = refill();
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardHeader>
                <CardTitle><h1 className="text-2xl font-semibold tracking-tight">{"Tea timer"}</h1></CardTitle>
                <CardDescription>{"Counts down from three minutes."}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-6">
                <span className="text-6xl font-semibold tracking-tight tabular-nums">{clock_text(seconds)}</span>
                {if running {
                    <Ticker onTick={handle_tick} />
                } elif finished {
                    <p className="text-sm font-medium text-primary">{"Done"}</p>
                } else {
                    <p className="text-sm font-medium text-muted-foreground">{"Ready"}</p>
                }}
                <div className="flex w-full gap-2">
                    <Button className="flex-1" onClick={handle_start}>{"Start"}</Button>
                    <Button className="flex-1" variant="outline" onClick={handle_reset}>{"Reset"}</Button>
                </div>
            </CardContent>
        </Card>
    </div>;
}
