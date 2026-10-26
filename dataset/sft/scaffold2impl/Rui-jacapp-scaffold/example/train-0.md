# Record

```json
{
  "source": "code",
  "format": "repo",
  "class": "fullstack",
  "task_type": "scaffold2impl",
  "fp": "Rui/pm::components/LoginPage.jac"
}
```

## SYSTEM

```
You are an expert AI assistant for the jac programming language. This is a chat interface, so write any Jac code you give as a ```jac fenced block.
```

## USER

Turn this Jac scaffold into a runnable file by writing every missing body. Return only the code.

```jac
import from "@jac/runtime" { jacLogin, jacSignup, jacIsLoggedIn, useNavigate, Navigate }

import from .ui.card { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter }
import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.label { Label }
import from .ui.field { Field, FieldLabel }

def:pub LoginPage -> JsxElement { ... }
```

## ASSISTANT

```jac
import from "@jac/runtime" { jacLogin, jacSignup, jacIsLoggedIn, useNavigate, Navigate }

import from .ui.card { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter }
import from .ui.button { Button }
import from .ui.input { Input }
import from .ui.label { Label }
import from .ui.field { Field, FieldLabel }

def:pub LoginPage -> JsxElement {
    has email: str = "";
    has password: str = "";
    has mode: str = "login";
    has status: str = "";
    has busy: bool = False;
    nav = useNavigate();

    if jacIsLoggedIn() {
        return <Navigate to="/" replace={True} />;
    }

    async def submit {
        if busy { return; }
        if not email.strip() or not password {
            status = "Enter email and password.";
            return;
        }
        busy = True;
        status = "";
        try {
            if mode == "signup" {
                signup_result: dict | None = None;
                signup_result = await jacSignup(email.strip(), password);
                if not signup_result["success"] {
                    status = "Signup failed (email may be in use).";
                    busy = False;
                    return;
                }
            }
            login_ok: bool = False;
            login_ok = await jacLogin(email.strip(), password);
            if not login_ok {
                status = "Invalid credentials.";
                busy = False;
                return;
            }
            nav("/");
        } except Exception as e {
            status = "Error: " + str(e);
        }
        busy = False;
    }

    return
        <div className="flex min-h-svh items-center justify-center bg-background p-6">
            <Card className="w-full max-w-sm">
                <CardHeader>
                    <CardTitle>{"Create account" if mode == "signup" else "Welcome back"}</CardTitle>
                    <CardDescription>
                        {"Sign up to start tracking projects." if mode == "signup" else "Log in to your PMSpace workspace."}
                    </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                    <Field>
                        <FieldLabel htmlFor="email">Email</FieldLabel>
                        <Input
                            id="email"
                            type="email"
                            value={email}
                            onChange={lambda (e: ChangeEvent) { email = e.target.value; }}
                            placeholder="you@example.com"
                        />
                    </Field>
                    <Field>
                        <FieldLabel htmlFor="password">Password</FieldLabel>
                        <Input
                            id="password"
                            type="password"
                            value={password}
                            onChange={lambda (e: ChangeEvent) { password = e.target.value; }}
                            onKeyPress={lambda (e: KeyboardEvent) {
                                if e.key == "Enter" { submit(); }
                            }}
                        />
                    </Field>
                    {(<p className="text-sm text-destructive">{status}</p>) if status else None}
                </CardContent>
                <CardFooter className="flex flex-col gap-2">
                    <Button className="w-full" onClick={submit} disabled={busy}>
                        {"Working..." if busy else ("Sign up" if mode == "signup" else "Log in")}
                    </Button>
                    <Button
                        className="w-full"
                        variant="ghost"
                        onClick={lambda { mode = "login" if mode == "signup" else "signup"; status = ""; }}
                    >
                        {"Have an account? Log in" if mode == "signup" else "Need an account? Sign up"}
                    </Button>
                </CardFooter>
            </Card>
        </div>;
}
```
