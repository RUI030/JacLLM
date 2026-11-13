# Risks

none. Every construct (plain-def handlers, `"a" if c else "b"` variant, `{for ... {<Button/>}}`, lambda onClick, a nested plain def called from the render body) appears in the verified calculator app. The one difference: `hours_text(chosen)` is called in the JSX body of the component (calculator calls its `show` only from handlers); it is a pure def with no await.
