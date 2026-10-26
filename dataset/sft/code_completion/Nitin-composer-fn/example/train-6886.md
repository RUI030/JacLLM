# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "function",
  "task_type": "code_completion",
  "fp": "380211",
  "origin_file": "composer_dataset.jsonl",
  "origin_id": 380211,
  "style": "idiomatic",
  "verification": "check+hidden_tests",
  "n_tokens": 256,
  "n_answer_tokens": 155
}
```

## SYSTEM

```
You are an expert jac language assistant.
```

## USER

Based on the header below, produce the corresponding Jac implementation.
"""Returns a len(y) + 1 by len(x) + 1 matrix, where the first row and column
    are filled with 0s and the rest is filled with -1s."""
def _get_edit_distance_matrix(x: str, y: str) -> list[list[int]] {

## ASSISTANT

"""Returns a len(y) + 1 by len(x) + 1 matrix, where the first row and column
    are filled with 0s and the rest is filled with -1s."""
def _get_edit_distance_matrix(x: str, y: str) -> list[list[int]] {
    matrix = [[-1 for _ in range(len(y) + 1)] for _ in range(len(x) + 1)];
    for j in range(len(matrix[0])) {
        matrix[0][j] = j;
    }
    for (i, _) in enumerate(matrix) {
        matrix[i][0] = i;
    }
    return matrix;
}
