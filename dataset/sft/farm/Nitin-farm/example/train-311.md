# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "function",
  "task_type": "farm",
  "fp": "Pseudo_Lab_PseudoTown__api_auth_models_py::UserModel",
  "origin_file": "farm_dataset.jsonl",
  "origin_id": "Pseudo_Lab_PseudoTown__api_auth_models_py::UserModel",
  "verification": "check+behavioral",
  "n_tokens": 259,
  "n_answer_tokens": 143
}
```

## SYSTEM

```
You are an expert jac language assistant.
```

## USER

You are given a Jac graph schema. Write walker:pub archetypes that create, list, delete, and (if appropriate) update instances of 'UserModel'. Reply with the code only.

```jac
node UserId {
    has user_id: int;
}

node UserModel {
    has user_id: int;
    has name: str;
    has discord: str;
}
```

## ASSISTANT

walker:pub create_UserModel {
    has user_id: int; has name: str; has discord: str;
    can go with Root entry { new = here ++> UserModel(user_id=self.user_id, name=self.name, discord=self.discord); report new; }
}
walker:pub list_UserModel { can go with Root entry { report [-->[?:UserModel]]; } }
walker:pub update_UserModel { has val: int; can go with UserModel entry { here.user_id = self.val; report here; } }
walker:pub delete_UserModel { can go with UserModel entry { del here; report "deleted"; } }
