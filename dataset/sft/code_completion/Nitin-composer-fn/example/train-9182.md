# Record

```json
{
  "source": "code",
  "format": "jac",
  "class": "function",
  "task_type": "code_completion",
  "fp": "270648",
  "origin_file": "composer_dataset.jsonl",
  "origin_id": 270648,
  "style": "floor",
  "verification": "check+hidden_tests",
  "n_tokens": 283,
  "n_answer_tokens": 128
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

Here is the start of a Jac function. Complete it and return the whole file.
"""If condition is False, then returns msg, otherwise returns empty string.

    :param bool condition: Condition paramater.
    :param str msg: Message returned if condition is False.
    :return: msg or empty string.
    :rtype: str


    >>> getMessageIfFalse(False, "Condition is set to False.")
    'Condition is set to False.'

    """
def getMessageIfFalse(condition: Any, msg: Any) -> object {

## ASSISTANT

"""If condition is False, then returns msg, otherwise returns empty string.

    :param bool condition: Condition paramater.
    :param str msg: Message returned if condition is False.
    :return: msg or empty string.
    :rtype: str


    >>> getMessageIfFalse(False, "Condition is set to False.")
    'Condition is set to False.'

    """
def getMessageIfFalse(condition: Any, msg: Any) -> object {
    if condition {
        return "";
    } else {
        return msg;
    }
}
