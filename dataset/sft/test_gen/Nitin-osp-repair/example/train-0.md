# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "test_gen",
  "fp": "testfix__iss_luizanunciostoca__aurora-ai-native__437",
  "origin_file": "osp_repair/test_fix.jsonl",
  "origin_id": "testfix__iss_luizanunciostoca__aurora-ai-native__437",
  "verification": "jac_test_pass",
  "n_tokens": 2342,
  "n_answer_tokens": 1195
}
```

## SYSTEM

```
You are an expert AI assistant for the jac programming language. This is a chat interface, so write any Jac code you give as a ```jac fenced block.
```

## USER

Write a Jac test annex (`main.test.jac`) for the program below. Use `test "..." { }` blocks that exercise its public behavior. Return the complete file.

```jac
"""Aurora release intelligence: invalidate dependent state and stop on cycles."""

node CacheEntry {
    has title: str = "";
    has year: int = 0;
    has available: bool = True;
    has cache_key: str = "";
    has fresh: bool = True;
}

node ContextSnapshot {
    has title: str = "";
    has year: int = 0;
    has available: bool = True;
    has snapshot_key: str = "";
    has stale: bool = False;
    has conflicting_facts: bool = False;
}

node TemplateVersion {
    has title: str = "";
    has year: int = 0;
    has available: bool = True;
    has version: int = 0;
    has active: bool = True;
    has rollback_target: str = "";
}

node RouterPlan {
    has title: str = "";
    has year: int = 0;
    has available: bool = True;
    has route_name: str = "";
    has enabled: bool = True;
    has rollback_ready: bool = True;
}

edge DependsOn {
    has reason: str = "";
}

walker InvalidationSweep {
    has invalidated: int = 0;
    has seen_keys: list[str] = [];

    can start with Root entry {
        visit [->:DependsOn:->] else {
            disengage;
        }
    }

    can inspect_cache with CacheEntry entry {
        if here.cache_key in self.seen_keys {
            print(f"cycle detected at cache {here.cache_key}");
            disengage;
        }
        self.seen_keys.append(here.cache_key);
        here.fresh = False;
        here.available = False;
        self.invalidated = self.invalidated + 1;
        print(f"cache {here.cache_key} invalidated");
        visit [->:DependsOn:->] else {
            disengage;
        }
    }

    can inspect_context with ContextSnapshot entry {
        if here.snapshot_key in self.seen_keys {
            print(f"cycle detected at context {here.snapshot_key}");
            disengage;
        }
        self.seen_keys.append(here.snapshot_key);
        here.stale = True;
        here.available = False;
        self.invalidated = self.invalidated + 1;
        if here.conflicting_facts {
            print(f"conflicting facts rejected for {here.snapshot_key}");
        }
        print(f"context {here.snapshot_key} marked stale");
        visit [->:DependsOn:->] else {
            disengage;
        }
    }

    can inspect_template with TemplateVersion entry {
        if f"{here.version}" in self.seen_keys {
            print(f"cycle detected at template {here.version}");
            disengage;
        }
        self.seen_keys.append(f"{here.version}");
        here.active = False;
        here.available = False;
        self.invalidated = self.invalidated + 1;
        print(f"template v{here.version} rolled back to {here.rollback_target}");
        visit [->:DependsOn:->] else {
            disengage;
        }
    }

    can inspect_router with RouterPlan entry {
        if here.route_name in self.seen_keys {
            print(f"cycle detected at router {here.route_name}");
            disengage;
        }
        self.seen_keys.append(here.route_name);
        here.enabled = False;
        here.available = False;
        self.invalidated = self.invalidated + 1;
        print(f"router {here.route_name} disabled; safe fallback retained");
        visit [->:DependsOn:->] else {
            disengage;
        }
    }
}

with entry {
    cache = CacheEntry(title="response cache", cache_key="cache:answer");
    context = ContextSnapshot(
        title="release context",
        snapshot_key="ctx:42",
        conflicting_facts=True
    );
    template = TemplateVersion(
        title="prompt template",
        version=7,
        rollback_target="v6"
    );
    router = RouterPlan(
        title="adaptive router",
        route_name="router:adaptive"
    );

    root +>:DependsOn(reason="release inputs"):+> cache;
    cache +>:DependsOn(reason="cache depends on context"):+> context;
    context +>:DependsOn(reason="context selects template"):+> template;
    template +>:DependsOn(reason="template selects router"):+> router;
    router +>:DependsOn(reason="fault-injection cycle"):+> cache;

    root spawn InvalidationSweep();
}
```

## ASSISTANT

```jac
import io;
import from contextlib { redirect_stdout }

test "invalidate dependency chain and reject conflicts" {
    cache = CacheEntry(title="cache", cache_key="cache:answer");
    context = ContextSnapshot(
        title="context",
        snapshot_key="ctx:42",
        conflicting_facts=True
    );
    template = TemplateVersion(
        title="template",
        version=7,
        rollback_target="v6"
    );
    router = RouterPlan(
        title="router",
        route_name="router:adaptive"
    );

    root +>:DependsOn(reason="release inputs"):+> cache;
    cache +>:DependsOn(reason="cache depends on context"):+> context;
    context +>:DependsOn(reason="context selects template"):+> template;
    template +>:DependsOn(reason="template selects router"):+> router;

    assert len([root ->:DependsOn:->]) == 1, "root should have one dependency";
    assert cache in [root ->:DependsOn:->], "cache should depend directly on root";

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn InvalidationSweep();
    }
    out = buf.getvalue();

    assert res.invalidated == 4, f"expected four invalidations, got {res.invalidated}";
    assert cache.fresh == False, f"cache should be stale: {cache.fresh}";
    assert cache.available == False, f"cache should be unavailable: {cache.available}";
    assert context.stale == True, f"context should be stale: {context.stale}";
    assert context.available == False, f"context should be unavailable: {context.available}";
    assert template.active == False, f"template should be inactive: {template.active}";
    assert template.available == False, f"template should be unavailable: {template.available}";
    assert router.enabled == False, f"router should be disabled: {router.enabled}";
    assert router.available == False, f"router should be unavailable: {router.available}";
    assert "conflicting facts rejected for ctx:42" in out, f"missing conflict rejection: {out}";
    assert "template v7 rolled back to v6" in out, f"missing rollback output: {out}";
    assert "safe fallback retained" in out, f"missing fallback output: {out}";
}

test "stop invalidation on dependency cycle" {
    cache = CacheEntry(cache_key="cache:cycle");
    context = ContextSnapshot(snapshot_key="ctx:cycle");
    template = TemplateVersion(version=3, rollback_target="v2");
    router = RouterPlan(route_name="router:cycle");

    root +>:DependsOn(reason="start"):+> cache;
    cache +>:DependsOn(reason="context"):+> context;
    context +>:DependsOn(reason="template"):+> template;
    template +>:DependsOn(reason="router"):+> router;
    router +>:DependsOn(reason="cycle"):+> cache;

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn InvalidationSweep();
    }
    out = buf.getvalue();

    assert res.invalidated == 4, f"cycle should invalidate four unique nodes, got {res.invalidated}";
    assert cache.fresh == False, f"cache should be invalidated: {cache.fresh}";
    assert context.stale == True, f"context should be stale: {context.stale}";
    assert template.active == False, f"template should be rolled back: {template.active}";
    assert router.enabled == False, f"router should be disabled: {router.enabled}";
    assert "cycle detected at cache cache:cycle" in out, f"missing cycle detection: {out}";
}

test "rollback template and disable adaptive router" {
    template = TemplateVersion(
        title="candidate",
        version=9,
        rollback_target="v8"
    );
    router = RouterPlan(
        title="adaptive",
        route_name="router:adaptive",
        rollback_ready=True
    );

    root +>:DependsOn(reason="release rollback"):+> template;
    template +>:DependsOn(reason="router fallback"):+> router;

    buf = io.StringIO();
    with redirect_stdout(buf) {
        res = root spawn InvalidationSweep();
    }
    out = buf.getvalue();

    assert res.invalidated == 2, f"expected two invalidations, got {res.invalidated}";
    assert template.active == False, f"template should be inactive: {template.active}";
    assert template.available == False, f"template should be unavailable: {template.available}";
    assert router.enabled == False, f"router should be disabled: {router.enabled}";
    assert router.available == False, f"router should be unavailable: {router.available}";
    assert router.rollback_ready == True, f"rollback readiness should remain recorded: {router.rollback_ready}";
    assert "template v9 rolled back to v8" in out, f"missing template rollback: {out}";
    assert "router router:adaptive disabled; safe fallback retained" in out, f"missing router fallback: {out}";
}
```
