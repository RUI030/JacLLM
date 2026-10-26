# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "function",
  "task_type": "code_completion",
  "fp": "268553",
  "origin_file": "composer_dataset.jsonl",
  "origin_id": 268553,
  "style": "idiomatic",
  "verification": "check+hidden_tests",
  "n_tokens": 137,
  "n_answer_tokens": 56
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Finish the jac code below.
"""Return indices of primes from a precomputed sieve."""
def get_list_of_primes_pre_calc(gen: list[bool]) -> list[int] {

## ASSISTANT

"""Return indices of primes from a precomputed sieve."""
def get_list_of_primes_pre_calc(gen: list[bool]) -> list[int] {
    return [ind for (ind, i) in enumerate(gen) if i];
}
