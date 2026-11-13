"""analyze_project and find_symbol for the spike harness: jacBuilder jac_coder/tool/read/jac_analyzer.impl.jac on
jaclang's CodeIntelligence, same output wording, minus its sandbox, status and truncation helpers.

    jac run lookup.jac analyze <directory>
    jac run lookup.jac symbol <name> <directory>
"""

import os;
import sys;
import from jaclang.compiler.code_intel { CodeIntelligence }


def _rel_path(abs_path: str, base: str) -> str {
    try {
        return os.path.relpath(abs_path, base);
    } except Exception {
        return abs_path;
    }
}


def _format_symbol_short(symbol: any, base: str) -> str {
    kind = str(getattr(symbol, "kind", "?"));
    name = str(getattr(symbol, "name", "?"));
    rel_file = _rel_path(str(getattr(symbol, "file", "")), base);
    line = getattr(symbol, "line", 0);
    return f"{kind} {name} ({rel_file}:{line})";
}


def _format_symbol_full(symbol: any, base: str) -> str {
    lines: list[str] = [_format_symbol_short(symbol, base)];
    fields = list(getattr(symbol, "fields", []) or []);
    if fields {
        lines.append(f"  fields: {', '.join([str(getattr(f, 'name', f)) for f in fields[:10]])}");
    }
    abilities = list(getattr(symbol, "abilities", []) or []);
    if abilities {
        lines.append(f"  abilities: {', '.join([str(getattr(a, 'name', a)) for a in abilities[:10]])}");
    }
    bases = list(getattr(symbol, "base_classes", []) or []);
    if bases {
        lines.append(f"  base: {', '.join([str(b) for b in bases])}");
    }
    return "\n".join(lines);
}


def _intel(directory: str) -> CodeIntelligence | None {
    try {
        # type_check=True silently fails to index (JacCoder's note), so skip it.
        intel = CodeIntelligence(proj_dir=os.path.realpath(directory), type_check=False);
        intel.load();
        return intel;
    } except Exception {
        return None;
    }
}


def analyze_project(directory: str) -> str {
    if not os.path.isdir(directory) {
        return f"Error: directory not found: {directory}";
    }
    intel = _intel(directory);
    if intel is None {
        return f"Analysis failed: could not build CodeIntelligence for {directory}";
    }
    try {
        archetypes = list(intel.archetypes() or []);
    } except Exception as exc {
        return f"Analysis failed: {exc}";
    }
    if not archetypes {
        return f"No archetypes found in {directory}. The project may be empty or have only top-level scripts.";
    }
    by_kind: dict[str, list] = {};
    for a in archetypes {
        by_kind.setdefault(str(getattr(a, "kind", "other")), []).append(a);
    }
    sections: list[str] = [f"Project: {directory}", f"Found {len(archetypes)} archetype(s) across {len(by_kind)} kind(s).\n"];
    for kind in sorted(by_kind.keys()) {
        items = by_kind[kind];
        sections.append(f"== {kind} ({len(items)}) ==");
        for a in items[:20] {
            sections.append(_format_symbol_full(a, directory));
        }
        if len(items) > 20 {
            sections.append(f"  ... and {len(items) - 20} more {kind}(s)");
        }
        sections.append("");
    }
    return "\n".join(sections);
}


def find_symbol(name: str, directory: str) -> str {
    if not name {
        return "Error: symbol name is required.";
    }
    if not directory or not os.path.isdir(directory) {
        return f"Error: valid directory is required (got: '{directory}').";
    }
    intel = _intel(directory);
    if intel is None {
        return f"Analysis failed: could not build CodeIntelligence for {directory}";
    }
    try {
        hits = list(intel.lookup(name) or []);
    } except Exception as exc {
        return f"Lookup failed: {exc}";
    }
    try {
        refs = list(intel.references(name) or []);
    } except Exception {
        refs = [];
    }
    if not hits and not refs {
        return f"Symbol '{name}' not found in the project.";
    }
    output: list[str] = [];
    if hits {
        output.append(f"Found {len(hits)} definition(s) of '{name}':");
        for h in hits {
            output.append(_format_symbol_full(h, directory));
        }
        if any([str(getattr(h, "kind", "")) == "node" for h in hits]) {
            try {
                visits = list(intel.walkers_visiting(name) or []);
                if visits {
                    output.extend(["", f"Walkers visiting '{name}':"]);
                    for v in visits[:20] {
                        rel = _rel_path(str(getattr(v, "file", "")), directory);
                        output.append(f"  {getattr(v, 'walker_name', '?')}.{getattr(v, 'ability', '')} "
                                      f"({getattr(v, 'event', '')}) — {rel}:{getattr(v, 'line', 0)}");
                    }
                }
            } except Exception { }
        }
    }
    uses = [r for r in refs if str(getattr(r, "role", "")) != "def"];
    if uses {
        output.extend(["", f"Used at {len(uses)} location(s):"]);
        for u in uses[:20] {
            output.append(f"  {_rel_path(str(getattr(u, 'file', '')), directory)}:{getattr(u, 'line', 0)}");
        }
        if len(uses) > 20 {
            output.append(f"  ... and {len(uses) - 20} more");
        }
    }
    return "\n".join(output);
}


with entry {
    args = sys.argv[1:];
    if args and args[0] == "analyze" and len(args) == 2 {
        print(analyze_project(args[1]));
    } elif args and args[0] == "symbol" and len(args) == 3 {
        print(find_symbol(args[1], args[2]));
    } else {
        print("usage: jac run lookup.jac analyze <directory> | symbol <name> <directory>");
    }
}
