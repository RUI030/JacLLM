# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "function",
  "task_type": "code_completion",
  "fp": "313814",
  "origin_file": "composer_dataset.jsonl",
  "origin_id": 313814,
  "style": "idiomatic",
  "verification": "check+hidden_tests",
  "n_tokens": 139,
  "n_answer_tokens": 65
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Here is the start of a Jac function. Complete it and return the whole file.
"""Returns a dictionary of headers with authorization token."""
def init_headers(token: str) -> dict[str, str] {

## ASSISTANT

"""Returns a dictionary of headers with authorization token."""
def init_headers(token: str) -> dict[str, str] {
  headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  };
  return headers;
}
