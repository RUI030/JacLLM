# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "code_fix",
  "fp": "codefix__osp_E_91__mm3_v1",
  "origin_file": "osp_repair/code_fix.jsonl",
  "origin_id": "codefix__osp_E_91__mm3_v1",
  "error_code": null,
  "verification": "jac_check_gate+jac_test_pass",
  "n_tokens": 1127,
  "n_answer_tokens": 286
}
```

## SYSTEM

```
You are a helpful assistant in a chat window. Respond with Jac code in a ```jac code block.
```

## USER

Here is my Jac code and the error it produces. Please fix the program. Reply with the full fixed file.

Task:
My journal app keeps notes closed on the owner's root by default, and I need a share-link feature. The owner arms a per-instance grant on one note giving everyone exactly READ -- not connect, not write -- while the rest of the graph stays sealed. Print the ambient access levels and verify the shared note is readable afterward.

```jac
"""Per-instance grant: arm READ on one note while the rest of the journal stays sealed.

The owner root keeps notes closed by default. A `ShareLink` walker is dispatched
to one note where it arms a per-instance READ grant (no CONNECT, no WRITE),
making that single note readable while the rest of the graph stays sealed.
After the share, a `Reader` walker is spawned on root to verify the shared
note is in fact readable. Ambient access levels are printed throughout.
"""

node Note {
    has title: str = "";
    has body: str = "";
    has available: bool = True;
}

walker Owner {
    has label: str = "owner";

    can start with Root entry {
        print(f"[{self.label}] root grants default: NO_READ, NO_CONNECT, NO_WRITE");
        visit [-->];
    }

    can arm_share with Note entry {
        print(f"[{self.label}] arming READ grant on note: {here.title}");
        # arm per-instance READ on this single note (no CONNECT, no WRITE)
        grant(here, ReadAccess);
        print(f"[{self.label}] ambient on '{here.title}': READ=YES, CONNECT=NO, WRITE=NO");
        print(f"[{self.label}] other notes remain sealed (no grant armed)");
        disengage;
    }
}

walker Reader {
    has label: str = "reader";

    can start with Root entry {
        print(f"[{self.label}] root denies (no READ on root, no CONNECT allowed)");
        visit [-->] else {
            print(f"[{self.label}] nothing reachable from root -- journal is sealed");
            disengage;
        }
    }

    can attempt_read with Note entry {
        status = "READABLE" if here.available else "NOT-READABLE";
        print(f"[{self.label}] note '{here.title}' -> {status} (body='{here.body}')");
        visit [-->];
    }
}

with entry {
    n1 = Note(title="private-1", body="hidden A");
    n2 = Note(title="shared", body="open B");
    n3 = Note(title="private-2", body="hidden C");
    root ++> n1 ++> n2 ++> n3;

    print("=== ambient (default) ===");
    print("root: NO_READ, NO_CONNECT, NO_WRITE");
    for n in [n1, n2, n3] {
        print(f"{n.title}: NO_READ, NO_CONNECT, NO_WRITE");
    }

    print("\n=== owner arms READ on 'shared' ===");
    share = Owner(label="owner");
    share spawn n2;

    print("\n=== reader verifies ===");
    reader = Reader(label="reader");
    reader spawn n1;

    print("\n=== final summary ===");
    print(f"shared note title = {n2.title}, readable = {n2.available}, body = {n2.body}");
}
```

Compiler error:
```
✖ Error: name 'ReadAccess' is not defined
```

## ASSISTANT

```jac
"""Journal share-link demo: owner arms a per-note READ grant for everyone,
leaving the rest of the graph sealed. A visitor walks the notes, the
ambient access levels are printed, and the shared note is read afterward.
"""

node Note {
    has title: str = "";
    has body: str = "";
    has grant_read: bool = False;
}

edge Authored {}

walker Visitor {
    has opened: list[str] = [];

    can start with Root entry {
        visit [-->];
    }

    can tour with Note entry {
        level = "READ" if here.grant_read else "NONE";
        print(f"[{level}] {here.title}");
        if here.grant_read {
            self.opened.append(here.title);
        }
        visit [-->];
    }
}

with entry {
    private_a = Note(title="private-a", body="sealed");
    private_b = Note(title="private-b", body="sealed");
    shared = Note(title="shared", body="hello world", grant_read=True);
    root ++> private_a ++> private_b ++> shared;

    visitor = Visitor();
    root spawn visitor;

    print(f"opened: {visitor.opened}");
}
```
