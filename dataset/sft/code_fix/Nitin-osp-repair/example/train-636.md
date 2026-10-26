# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "code_fix",
  "fp": "codefix__iss_matiaszanolli__ByroRedux__3662",
  "origin_file": "osp_repair/code_fix.jsonl",
  "origin_id": "codefix__iss_matiaszanolli__ByroRedux__3662",
  "error_code": "E1030",
  "verification": "jac_check_gate+jac_test_pass",
  "n_tokens": 3763,
  "n_answer_tokens": 1189
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

The Jac program below fails with the compiler error shown. Fix it and return the complete corrected program.

Task:
A maintainer on the project matiaszanolli/ByroRedux (unknown) filed this issue about hand-rolled graph machinery causing pain:

Issue #3662: PERF-D3-2026-08-30-02: the 80 % DEVICE_LOCAL "approaching OOM" warning has exactly one caller — at engine init, before any cell loads — so it can never fire under the pressure it exists to detect

- **Severity**: MEDIUM
- **Dimension**: GPU Memory Pressure
- **Location**: `crates/renderer/src/vulkan/allocator.rs:289-334`
  (`warn_threshold_bytes`, `log_memory_usage`),
  `crates/renderer/src/vulkan/context/resources.rs:430-433` (wrapper),
  `byroredux/src/app_events.rs:204` (sole call site),
  `docs/engine/memory-budget.md:555-560`
- **Status**: NEW
- **Description**: `memory-budget.md` closes the VRAM ledger with "A warning fires
  when total allocated bytes exceed 80% of the smallest DEVICE_LOCAL heap
  (`(heap / 5) * 4`, with a 2 GB fallback when no DEVICE_LOCAL heap is reported)."
  The formula is exactly right and matches
  `warn_threshold_bytes` verbatim. The *firing* is not: a workspace-wide grep
  finds `log_memory_usage` reachable from precisely one place —
  `App::resumed`, immediately before `log::info!("Engine ready — entering game loop")`.
  `step_streaming` and `step_debug_loads` run from `about_to_wait`
  (`app_events.rs:706, 715`), i.e. strictly after that sample, and nothing
  re-takes it: not per frame, not per cell load, not per cell unload, and not
  from any console command (`ctx.memory` / `mem.frag` read
  `generate_report` directly and never consult the threshold;
  `commands/world_info.rs:761-780`). The debug-UI metrics sampler
  (`byroredux/src/systems/metrics.rs:110-130`) does sample VRAM every tick, but
  it compares nothing, logs nothing, and uses `GpuMemoryBudget::total_vram_bytes`
  (the **sum** of DEVICE_LOCAL heaps) rather than `smallest_heap_bytes`, which is
  the tighter cap the guard was written against.
- **Evidence**:
  ```
  $ grep -rn "log_memory_usage" --include="*.rs" crates byroredux
  crates/renderer/src/vulkan/allocator.rs:304:pub fn log_memory_usage(          # definition
  crates/renderer/src/vulkan/context/resources.rs:432:    …allocator::log_memory_usage(  # wrapper
  byroredux/src/app_events.rs:204:  self.renderer.as_ref().unwrap().log_memory_usage();  # only caller
  ```
  ```rust
  // byroredux/src/app_events.rs:203-205
  self.scheduler.run(&self.world, 0.0);
  self.renderer.as_ref().unwrap().log_memory_usage();
  log::info!("Engine ready — entering game loop");
  ```
- **Impact**: The engine has no live VRAM-pressure signal. Every mechanism this
  dimension audits — BLAS LRU eviction, TLAS/scratch shrink, staging-pool trim,
  the texture bindless ceiling — degrades *quietly* by design (evict, fall back to
  the checkerboard handle, keep the oversized buffer), so the 80 % warn was the
  one place a session was told it was approaching the heap. On the 12 GB dev card
  the boot sample is ~0.3 GB against a ~9.6 GB threshold; on the 6 GB RT-minimum
  target the same sample is taken before the content that would breach 4.8 GB
  exists. Defense-in-depth gap, not a crash — hence MEDIUM.
- **Related**: #505 (which introduced the heap-scaled threshold precisely because
  the old 2 GB constant "warned on every large cell load" — that observation
  implies a call frequency the code no longer has). #2030's
  `check_slot_available` 90 % one-shot latch is the pattern that *does* work,
  because it sits on the allocation path.
- **Suggested Fix**: Call `log_memory_usage` from the cell-load / cell-unload
  boundary (`cell_loader::unload_cells`' finalization, or the end of
  `step_streaming`) with a one-shot `Once` latch on the WARN arm so a sustained
  breach logs once rather than per transition — the same shape
  `check_slot_available` already uses. Optionally reword
  `memory-budget.md:555-560` to say *when* it samples.

## Completeness Checks
- [ ] **UNSAFE**: If the fix adds `unsafe`, a safety comment states the upheld invariant
- [ ] **SIBLING**: Same pattern checked in related files (other shader types, other block parsers)
- [ ] **DROP**: If Vulkan objects change, the Drop impl is still reverse-order correct
- [ ] **LOCK_ORDER**: If a RwLock scope changes, TypeId-sorted acquisition is preserved
- [ ] **CANONICAL-BOUNDARY**: If the fix touches `byroredux/src/material_translate.rs` (`translate_material`), `Material::resolve_pbr` (`crates/core/src/ecs/components/material.rs`), or the emitter params in `crates/nif/src/import/walk/mod.rs` (`extract_emitter_params` / `extract_emitter_rate`), per-game logic stays at the NIFAL parser→`Material` boundary — never pushed into shaders/renderer, never re-derived at render time. See `/audit-nifal`.
- [ ] **TESTS**: A regression test pins this specific fix

---
*Filed from `docs/audits/AUDIT_PERFORMANCE_2026-08-30.md` (HEAD `64f64480`). Report status: NEW; re-verified CONFIRMED against HEAD at publish time.*


Write a small self-contained Jac demo program that models the essential scenario from this issue natively: pick the 2-4 core entity types as node archetypes with typed has fields, connect instances with edges (typed edges where the relationship carries meaning), and implement walker(s) that perform the traversal the issue complains about (e.g. recursion over parents/children, cascade delete or invalidation, dependency ordering, cycle detection, reachability). Wire a small demonstration graph in a `with entry` block and spawn the walker(s). No I/O, no external libraries, no pytest blocks.

```jac
"""GPU VRAM pressure audit: model cell-load/unload boundaries as a typed-edge graph
and walk it with a pressure-sampling walker that mirrors the bug in the issue —
the 80 % DEVICE_LOCAL warn fires exactly once at engine init and never again
under the streaming/transitions it exists to detect."""

node Cell {
    has name: str = "";
    has vram_bytes: int = 0;
}

node Heap {
    has label: str = "";
    has size_bytes: int = 0;
}

node Frame {
    has tick: int = 0;
}

edge Loaded {
    has at_tick: int = 0;
}

walker PressureSampler {
    has smallest_heap_bytes: int = 0;
    has warn_pct: float = 0.8;
    has warned: bool = False;
    has current_vram: int = 0;

    can start with Root entry {
        visit [->:Loaded:->];
    }

    can sample with Heap entry {
        if self.smallest_heap_bytes == 0
            or self.smallest_heap_bytes > self.here.size_bytes {
            self.smallest_heap_bytes = self.here.size_bytes;
        }
        visit [->:Loaded:->];
    }

    can measure with Cell entry {
        self.current_vram = self.current_vram + self.here.vram_bytes;
        visit [->:Loaded:->];
    }

    can check with Frame entry {
        threshold = int(self.smallest_heap_bytes * self.warn_pct);
        if self.current_vram >= threshold {
            if not self.warned {
                print(f"[WARN] tick={self.here.tick} "
                      + f"vram={self.current_vram} "
                      + f">= 80% of smallest DEVICE_LOCAL heap ({threshold})");
                self.warned = True;
            } else {
                print(f"[silent] tick={self.here.tick} "
                      + f"vram={self.current_vram} still over threshold "
                      + f"({threshold}) — latch suppresses re-fire");
            }
        } else {
            print(f"[ok]   tick={self.here.tick} "
                  + f"vram={self.current_vram} / {threshold}");
        }
        visit [-->];
    }
}

walker EngineBoot {
    has vram_at_boot: int = 0;

    can start with Root entry {
        print(f"[boot] one-shot VRAM sample = {self.vram_at_boot} bytes "
              + "— fires the warn if already over the threshold, then goes silent");
        visit [-->];
    }
}

with entry {
    gpu_small = Heap(label="DEVICE_LOCAL#0", size_bytes=12 * 1024 * 1024 * 1024);
    gpu_large = Heap(label="DEVICE_LOCAL#1", size_bytes=24 * 1024 * 1024 * 1024);
    root ++> gpu_small ++> gpu_large;

    terrain   = Cell(name="terrain",   vram_bytes= 2 * 1024 * 1024 * 1024);
    foliage   = Cell(name="foliage",   vram_bytes= 3 * 1024 * 1024 * 1024);
    creatures = Cell(name="creatures", vram_bytes= 1 * 1024 * 1024 * 1024);

    gpu_large +>:Loaded(at_tick=0):+> terrain;
    gpu_large +>:Loaded(at_tick=1):+> foliage;
    gpu_large +>:Loaded(at_tick=2):+> creatures;

    f0 = Frame(tick=0);
    f1 = Frame(tick=1);
    f2 = Frame(tick=2);
    f3 = Frame(tick=3);

    terrain   ++> f0;
    foliage   ++> f1;
    creatures ++> f2;
    creatures ++> f3;

    boot = EngineBoot(vram_at_boot=300 * 1024 * 1024);
    root spawn boot;

    sampler = PressureSampler();
    root spawn sampler;
}
```

Compiler error:
```
✖ Error: error[E1030]: Type "PressureSampler" has no attribute "here"
```

## ASSISTANT

"""GPU VRAM pressure audit: model cell-load/unload boundaries as a typed-edge graph
and walk it with a pressure-sampling walker that mirrors the bug in the issue —
the 80 % DEVICE_LOCAL warn fires exactly once at engine init and never again
under the streaming/transitions it exists to detect."""

node Cell {
    has name: str = "";
    has vram_bytes: int = 0;
}

node Heap {
    has label: str = "";
    has size_bytes: int = 0;
}

node Frame {
    has tick: int = 0;
}

edge Loaded {
    has at_tick: int = 0;
}

walker PressureSampler {
    has smallest_heap_bytes: int = 0;
    has warn_pct: float = 0.8;
    has warned: bool = False;
    has current_vram: int = 0;
    has boot_vram: int = 0;

    can start with Root entry {
        visit [->:Loaded:->];
    }

    can sample_heap with Heap entry {
        here_size = here.size_bytes;
        if self.smallest_heap_bytes == 0
            or self.smallest_heap_bytes > here_size {
            self.smallest_heap_bytes = here_size;
        }
        visit [->:Loaded:->];
    }

    can measure_cell with Cell entry {
        here_vram = here.vram_bytes;
        self.current_vram = self.current_vram + here_vram;
        visit [-->];
    }

    can check_frame with Frame entry {
        threshold = int(self.smallest_heap_bytes * self.warn_pct);
        here_tick = here.tick;
        if self.current_vram >= threshold {
            if not self.warned {
                print(f"[WARN] tick={here_tick} "
                      + f"vram={self.current_vram} "
                      + f">= 80% of smallest DEVICE_LOCAL heap ({threshold})");
                self.warned = True;
            } else {
                print(f"[silent] tick={here_tick} "
                      + f"vram={self.current_vram} still over threshold "
                      + f"({threshold}) — latch suppresses re-fire");
            }
        } else {
            print(f"[ok]   tick={here_tick} "
                  + f"vram={self.current_vram} / {threshold}");
        }
        visit [-->];
    }
}

walker EngineBoot {
    has vram_at_boot: int = 0;
    has threshold_at_boot: int = 0;

    can start with Root entry {
        boot_vram = self.vram_at_boot;
        boot_threshold = self.threshold_at_boot;
        print(f"[boot] one-shot VRAM sample = {boot_vram} bytes; "
              + f"threshold at boot = {boot_threshold}");
        if boot_vram >= boot_threshold {
            print(f"[boot][WARN] already over the threshold at engine init — "
                  + "the warn is the only chance to surface this; "
                  + "nothing re-samples on streaming transitions");
        } else {
            print(f"[boot] under threshold; warn will not fire here, "
                  + "and nothing else will ever sample again (the bug)");
        }
        visit [-->];
    }
}

with entry {
    gpu_small = Heap(label="DEVICE_LOCAL#0", size_bytes=12 * 1024 * 1024 * 1024);
    gpu_large = Heap(label="DEVICE_LOCAL#1", size_bytes=24 * 1024 * 1024 * 1024);
    root ++> gpu_small ++> gpu_large;

    terrain   = Cell(name="terrain",   vram_bytes= 2 * 1024 * 1024 * 1024);
    foliage   = Cell(name="foliage",   vram_bytes= 3 * 1024 * 1024 * 1024);
    creatures = Cell(name="creatures", vram_bytes= 1 * 1024 * 1024 * 1024);

    gpu_large +>:Loaded(at_tick=0):+> terrain;
    gpu_large +>:Loaded(at_tick=1):+> foliage;
    gpu_large +>:Loaded(at_tick=2):+> creatures;

    f0 = Frame(tick=0);
    f1 = Frame(tick=1);
    f2 = Frame(tick=2);
    f3 = Frame(tick=3);

    terrain   ++> f0;
    foliage   ++> f1;
    creatures ++> f2;
    creatures ++> f3;

    boot_vram = 300 * 1024 * 1024;
    boot_threshold = int(gpu_small.size_bytes * 0.8);

    boot = EngineBoot(vram_at_boot=boot_vram, threshold_at_boot=boot_threshold);
    root spawn boot;

    sampler = PressureSampler(boot_vram=boot_vram);
    sampler.smallest_heap_bytes = gpu_small.size_bytes;
    root spawn sampler;
}
