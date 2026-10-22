"""Extract the code from a model reply (a ```jac fence if there is one, else the whole reply) + classify its shape."""

import re
from typing import Literal

_JAC_FENCE = re.compile(r"```jac\s*\n(.*?)```", re.DOTALL)
_ANY_FENCE = re.compile(r"```([A-Za-z0-9_+.-]*)\s*\n.*?```", re.DOTALL)

OutputKind = Literal["has_block", "bare", "wrong_fence", "no_output"]

THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


def extract_jac_blocks(text: str) -> list[str]:
    """Return every ```jac ... ``` block body, in order. Empty list if none."""
    return [m.group(1).strip() for m in _JAC_FENCE.finditer(text)]


def strip_think(text: str) -> str:
    """Reply without its reasoning: whatever follows the last `</think>`; a `<think>` never closed (cut off) leaves nothing."""
    if THINK_CLOSE in text:
        return text.rsplit(THINK_CLOSE, 1)[-1]
    return text.split(THINK_OPEN, 1)[0] if THINK_OPEN in text else text


def extract_code(text: str) -> str | None:
    """Code of a reply: the first ```jac block if any, else the whole reply (a bare-code answer), reasoning removed.

    None when the reply has nothing but other-language fences or is empty.
    """
    text = strip_think(text)
    block = first_jac_block(text)
    if block is not None:
        return block
    if _ANY_FENCE.search(text):
        return None
    return text.strip() or None


def first_jac_block(text: str) -> str | None:
    """Return the first ```jac ... ``` block body, or None if absent."""
    blocks = extract_jac_blocks(text)
    return blocks[0] if blocks else None


def classify_output(text: str) -> OutputKind:
    """Coarse shape of the LLM output. Independent of code validity.

    - has_block    : ≥1 well-formed ```jac ... ``` fence
    - wrong_fence  : ≥1 fenced block but none labelled jac (```python, bare ```, etc.)
    - bare         : no fence; the whole reply is taken as code
    - no_output    : nothing left after the reasoning is removed
    """
    text = strip_think(text)
    if _JAC_FENCE.search(text):
        return "has_block"
    if _ANY_FENCE.search(text):
        return "wrong_fence"
    return "bare" if text.strip() else "no_output"
