# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "function",
  "task_type": "farm",
  "fp": "B21_CAP0076_backend__models_book_py::Book",
  "origin_file": "farm_dataset.jsonl",
  "origin_id": "B21_CAP0076_backend__models_book_py::Book",
  "verification": "check+behavioral",
  "n_tokens": 240,
  "n_answer_tokens": 150
}
```

## SYSTEM

```
You are an expert AI assistant specializing in the jac programming language.
```

## USER

Implement the CRUD walkers for the 'Book' node in the schema below. Output the walkers only.

```jac
node Book {
    has img: str;
    has title: str;
    has authors: list[str];
    has genres: list[str];
}
```

## ASSISTANT

walker:pub create_Book {
    has img: str; has title: str; has authors: list[str]; has genres: list[str];
    can go with Root entry { new = here ++> Book(img=self.img, title=self.title, authors=self.authors, genres=self.genres); report new; }
}
walker:pub list_Book { can go with Root entry { report [-->[?:Book]]; } }
walker:pub update_Book { has val: str; can go with Book entry { here.title = self.val; report here; } }
walker:pub delete_Book { can go with Book entry { del here; report "deleted"; } }
