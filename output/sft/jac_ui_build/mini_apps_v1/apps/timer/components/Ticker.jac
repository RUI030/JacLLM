import from react { useEffect }

def:pub Ticker(onTick: Callable[[], None]) -> JsxElement {
    useEffect(lambda {
        tick_cb = onTick;
        interval = setInterval(lambda { tick_cb.call(None); }, 1000);
        return lambda { clearInterval(interval); };
    }, []);
    return <p className="text-sm font-medium text-primary">{"Running"}</p>;
}
