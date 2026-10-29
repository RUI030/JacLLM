"""Measure chat-template size of observed JacCoder calls/results; not an SFT export."""

import argparse
import json
from pathlib import Path


# Setting =================================================
TOKENIZER = "ornith-ai/Ornith-1.5-9B"


# Functions ===============================================
def count(capture: dict, request_index: int, dispatch_start: int, dispatch_end: int,
          tokenizer_name: str = TOKENIZER) -> dict:
    from transformers import AutoTokenizer

    request = capture["requests"][request_index]
    tools = request["tools"]
    messages = list(request["messages"])
    dispatches = capture["dispatches"][dispatch_start:dispatch_end]
    names = {tool["function"]["name"] for tool in tools}
    for index, dispatch in enumerate(dispatches, 1):
        if dispatch["name"] not in names:
            raise ValueError(f"Call absent from selected request schema: {dispatch['name']}")
        call_id = f"budget-call-{index}"
        messages.append({
            "role": "assistant", "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": dispatch["name"], "arguments": dispatch["args"]},
            }],
        })
        messages.append({**dispatch["result"], "tool_call_id": call_id})
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, local_files_only=True)
    rendered = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)
    return {"tokenizer": tokenizer_name, "tool_count": len(tools),
            "observed_calls": [d["name"] for d in dispatches], "messages": len(messages),
            "tokens": len(tokenizer(rendered, add_special_tokens=False)["input_ids"]),
            "packing_note": "Observed calls/results were packed with generated pairing IDs; this is a budget measurement, not a recorded model response."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--request-index", type=int, required=True)
    parser.add_argument("--dispatch-start", type=int, default=0)
    parser.add_argument("--dispatch-end", type=int)
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text())
    end = len(capture["dispatches"]) if args.dispatch_end is None else args.dispatch_end
    print(json.dumps(count(capture, args.request_index, args.dispatch_start, end), indent=2))


# Run =====================================================
if __name__ == "__main__":
    main()
