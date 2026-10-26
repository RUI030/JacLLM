# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "function",
  "task_type": "farm",
  "fp": "rajat45mishra_cobraframework__modules_user_user_business_dtos_role_py::Role",
  "origin_file": "farm_dataset.jsonl",
  "origin_id": "rajat45mishra_cobraframework__modules_user_user_business_dtos_role_py::Role",
  "verification": "check+behavioral",
  "n_tokens": 222,
  "n_answer_tokens": 116
}
```

## SYSTEM

```
You are a helpful assistant in a chat window. Respond with Jac code in a ```jac code block.
```

## USER

Given the following Jac graph schema, write CRUD walkers (create, list, delete, and update where applicable) for the 'Role' node. Respond with only the code.

```jac
node Role {
    has rolename: str;
    has permissions: list[str];
    has unique_fields: list;
}
```

## ASSISTANT

```jac
walker:pub create_Role {
    has rolename: str; has permissions: list[str]; has unique_fields: list;
    can go with Root entry { new = here ++> Role(rolename=self.rolename, permissions=self.permissions, unique_fields=self.unique_fields); report new; }
}
walker:pub list_Role { can go with Root entry { report [-->[?:Role]]; } }
walker:pub delete_Role { can go with Role entry { del here; report "deleted"; } }
```
