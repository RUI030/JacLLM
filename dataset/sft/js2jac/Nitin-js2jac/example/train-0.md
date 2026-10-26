# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "fullstack",
  "task_type": "js2jac",
  "fp": "wleci__nextjs-fullstack-starter::lib/email/templates/welcome.tsx",
  "origin_file": "js2jac_dataset_idiomatic.jsonl",
  "origin_id": "wleci__nextjs-fullstack-starter::lib/email/templates/welcome.tsx",
  "verification": "check",
  "n_tokens": 811,
  "n_answer_tokens": 358
}
```

## SYSTEM

```
You are an expert AI assistant specializing in the jac programming language.
```

## USER

Rewrite the code below in Jac. Reply with only the Jac source.
```ts
import { Button, Heading, Text } from "@react-email/components";
import { BaseEmail } from "./base";
import { env } from "@/lib/env";

interface WelcomeProps {
    name: string;
    loginUrl: string;
}

export function Welcome({ name, loginUrl }: WelcomeProps) {
    return (
        <BaseEmail preview={`Welcome to ${env.NEXT_PUBLIC_APP_NAME}!`}>
            <Heading style={heading}>Welcome to {env.NEXT_PUBLIC_APP_NAME}!</Heading>
            <Text style={paragraph}>Hi {name},</Text>
            <Text style={paragraph}>
                Thanks for joining us! Your account is now ready. You can start using
                all features right away.
            </Text>
            <Button style={button} href={loginUrl}>
                Go to Dashboard
            </Button>
            <Text style={paragraph}>
                If you have any questions, feel free to reach out to our support team.
            </Text>
        </BaseEmail>
    );
}

const heading = {
    fontSize: "24px",
    fontWeight: "bold",
    marginBottom: "24px",
};

const paragraph = {
    fontSize: "14px",
    lineHeight: "24px",
    color: "#525f7f",
};

const button = {
    backgroundColor: "#000",
    borderRadius: "6px",
    color: "#fff",
    fontSize: "14px",
    fontWeight: "bold",
    textDecoration: "none",
    textAlign: "center" as const,
    display: "block",
    padding: "12px 24px",
    margin: "24px 0",
};
```

## ASSISTANT

import from "@react-email/components" { Button, Heading, Text }
import from "./base" { BaseEmail }
import from "@/lib/env" { env }

glob heading = {"fontSize": "24px", "fontWeight": "bold", "marginBottom": "24px"};

glob paragraph = {"fontSize": "14px", "lineHeight": "24px", "color": "#525f7f"};

glob button = {"backgroundColor": "#000", "borderRadius": "6px", "color": "#fff", "fontSize": "14px", "fontWeight": "bold", "textDecoration": "none", "textAlign": "center", "display": "block", "padding": "12px 24px", "margin": "24px 0"};

def:pub Welcome(name: str, loginUrl: str) -> JsxElement {
    return <BaseEmail preview={f"Welcome to {env.NEXT_PUBLIC_APP_NAME}!"}>
        <Heading style={heading}>Welcome to {env.NEXT_PUBLIC_APP_NAME}!</Heading>
        <Text style={paragraph}>Hi {name},</Text>
        <Text style={paragraph}>
            Thanks for joining us! Your account is now ready. You can start using
            all features right away.
        </Text>
        <Button style={button} href={loginUrl}>
            Go to Dashboard
        </Button>
        <Text style={paragraph}>
            If you have any questions, feel free to reach out to our support team.
        </Text>
    </BaseEmail>;
}
