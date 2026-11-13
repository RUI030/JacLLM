import from .ui.button { Button }
import from .ui.card { Card, CardHeader, CardTitle, CardDescription, CardContent }
import from .Ticker { Ticker }

glob _elapsed: int = 0;

def next_second() -> int {
    _elapsed = _elapsed + 1;
    return _elapsed;
}

def clear_seconds() -> int {
    _elapsed = 0;
    return _elapsed;
}

def fmt(total: int) -> str {
    secs = total % 60;
    mins = (total - secs) / 60;
    return str(mins) + ":" + str(secs).zfill(2);
}

def:pub Stopwatch() -> JsxElement {
    has seconds: int = 0;
    has running: bool = False;

    def handle_tick() { seconds = next_second(); }
    def handle_start(e: MouseEvent) {
        if not running {
            running = True;
        }
    }
    def handle_stop(e: MouseEvent) { running = False; }
    def handle_reset(e: MouseEvent) {
        running = False;
        seconds = clear_seconds();
    }

    return <div className="flex min-h-svh items-center justify-center bg-muted/40 pl-6 pr-6">
        <Card className="w-full max-w-sm shadow-sm">
            <CardHeader>
                <CardTitle><h1 className="text-2xl font-semibold tracking-tight">{"Stopwatch"}</h1></CardTitle>
                <CardDescription>{"Counts up once a second while it runs."}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-6">
                <span className="text-6xl font-semibold tracking-tight tabular-nums">{fmt(seconds)}</span>
                {if running {
                    <Ticker onTick={handle_tick} />
                } else {
                    <p className="text-sm font-medium text-muted-foreground">{"Stopped"}</p>
                }}
                <div className="flex w-full gap-2">
                    <Button className="flex-1" onClick={handle_start}>{"Start"}</Button>
                    <Button className="flex-1" variant="outline" onClick={handle_stop}>{"Stop"}</Button>
                    <Button className="flex-1" variant="outline" onClick={handle_reset}>{"Reset"}</Button>
                </div>
            </CardContent>
        </Card>
    </div>;
}
