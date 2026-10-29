"""Count a representative M0 exchange with the current SFT default tokenizer."""

import json
from pathlib import Path

from transformers import AutoTokenizer


# Setting =================================================
TOKENIZER = "ornith-ai/Ornith-1.5-9B"
CAPTURE   = Path(__file__).resolve().parents[1] / "trajectory/harness/jaccoder.m0.json"

# Functions ===============================================
def main() -> None:
    capture = json.loads(CAPTURE.read_text())
    tools = capture["tools"]
    messages = [
        {"role": "system", "content": capture["system"]},
        {"role": "user", "content": capture["request_user_message"]},
    ]
    write_dispatch = next(x for x in capture["dispatches"] if x["name"] == "write_code")
    messages.extend(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "m0-write-1",
                        "type": "function",
                        "function": {
                            "name": "write_code",
                            "arguments": {
                                **write_dispatch["args"],
                            },
                        },
                    }
                ],
            },
            {**write_dispatch["result"], "tool_call_id": "m0-write-1"},
            {"role": "assistant", "content": "The task tracker scaffold is ready."},
        ]
    )
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    rendered = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)
    count = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
    print(json.dumps({"model": TOKENIZER, "messages": len(messages), "tools": len(tools), "tokens": count}))


# Run =====================================================
if __name__ == "__main__":
    main()
