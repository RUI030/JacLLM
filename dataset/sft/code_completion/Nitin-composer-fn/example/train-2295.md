# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "function",
  "task_type": "code_completion",
  "fp": "203077",
  "origin_file": "composer_dataset.jsonl",
  "origin_id": 203077,
  "style": "idiomatic",
  "verification": "check+hidden_tests",
  "n_tokens": 211,
  "n_answer_tokens": 102
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Continue this Jac source. Return the complete file.
"""
Utility function will pick either the custom overriden value or the default
value for the row.
"""
def get_processed_row(data: dict[str, str | int | float | bool | None], key: str) -> str | int | float | bool | None {

## ASSISTANT

"""
Utility function will pick either the custom overriden value or the default
value for the row.
"""
def get_processed_row(data: dict[str, str | int | float | bool | None], key: str) -> str | int | float | bool | None {
    override_key = key + '_r';
    if data[override_key] {
        return data[override_key];
    }
    return data[key];
}
