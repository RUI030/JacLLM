"""Compiler AST bridge for reverse-development reference manifests."""

import json;
import os;
import sys;
import from pathlib { Path }
import from jaclang.jac0core.program { JacProgram }
import from jaclang.compiler.code_intel { CodeIntelligence }
import jaclang.jac0core.unitree as uni;

def span(item_node: any) -> dict {
    loc = item_node.loc;
    if loc is None {
        return {};
    }
    return {
        "line": loc.first_line, "column": loc.col_start,
        "end_line": loc.last_line, "end_column": loc.col_end
    };
}

def item_name(item: any) -> str {
    value = getattr(item, "name", None);
    return str(getattr(value, "value", "")) if value is not None else "";
}

def belongs(item_node: any, path: str) -> bool {
    loc = item_node.loc;
    return loc is not None and os.path.realpath(loc.mod_path) == os.path.realpath(path);
}

def declaration_head(source: str, item_node: any) -> str {
    loc = item_node.loc;
    if loc is None or loc.first_line < 1 {
        return "";
    }
    lines = source.splitlines();
    start = sum([len(line) + 1 for line in lines[:loc.first_line - 1]]) + loc.col_start - 1;
    segment = source[start:];
    brace = segment.find("{");
    semi = segment.find(";");
    ends = [n for n in [brace, semi] if n >= 0];
    return segment[:min(ends)].strip() if ends else segment.splitlines()[0].strip();
}

with entry {
    request_path = sys.argv[1];
    output_path = sys.argv[2];
    with open(request_path, "r", encoding="utf-8") as f {
        request = json.load(f);
    }
    repo = request["repo"];
    extracted: list = [];
    for record in request["files"] {
        path = record["path"];
        full_path = os.path.join(repo, path);
        source: str = Path(full_path).read_text(encoding="utf-8");
        try {
            prog = JacProgram();
            mod = prog.parse_str(source, full_path);
            imports: list = [];
            symbols: list = [];
            calls: list = [];
            for imp in mod.get_all_sub_nodes(uni.Import) {
                if not belongs(imp, full_path) { continue; }
                origin = imp.from_loc;
                items: list = [];
                for item in imp.items {
                    items.append({
                        "kind": type(item).__name__,
                        "name": item_name(item),
                        "path": str(getattr(item, "dot_path_str", "")),
                        "alias": str(getattr(getattr(item, "alias", None), "value", "")),
                        "span": span(item)
                    });
                }
                imports.append({
                    "from_path": str(getattr(origin, "dot_path_str", "")),
                    "from_level": getattr(origin, "level", 0),
                    "from_string": getattr(origin, "string_path_value", None),
                    "items": items,
                    "span": span(imp)
                });
            }
            for arch in mod.get_all_sub_nodes(uni.Archetype) {
                if not belongs(arch, full_path) { continue; }
                symbols.append({"kind": str(arch.arch_kind or "archetype"),
                    "name": str(arch.name.value), "signature": declaration_head(source, arch),
                    "fields": [{"name": str(field.name.value),
                        "declaration": str(field.unparse()), "span": span(field)}
                        for field in arch.get_has_vars() if belongs(field, full_path)],
                    "base_classes": [str(base.unparse()) for base in (arch.base_classes or [])],
                    "span": span(arch)});
            }
            for enum in mod.get_all_sub_nodes(uni.Enum) {
                if not belongs(enum, full_path) { continue; }
                symbols.append({"kind": "enum", "name": str(enum.name.value),
                    "signature": declaration_head(source, enum), "span": span(enum)});
            }
            for ability in mod.get_all_sub_nodes(uni.Ability) {
                if not belongs(ability, full_path) { continue; }
                name = ability.name_ref;
                owner = ability.method_owner;
                compiler_name = str(getattr(name, "value", ""));
                is_entry = compiler_name.startswith("__ability_entry_");
                symbols.append({"kind": "entry_ability" if is_entry else "ability",
                    "name": "with entry" if is_entry else compiler_name,
                    "compiler_name": compiler_name,
                    "owner": str(owner.name.value) if owner is not None else None,
                    "entry_point_role": "event_handler" if is_entry else None,
                    "signature": declaration_head(source, ability), "span": span(ability)});
            }
            for impl in mod.get_all_sub_nodes(uni.ImplDef) {
                if not belongs(impl, full_path) { continue; }
                symbols.append({"kind": "impl", "name": ".".join([str(getattr(n, "value", "")) for n in impl.target]),
                    "signature": declaration_head(source, impl), "span": span(impl)});
            }
            for call in mod.get_all_sub_nodes(uni.FuncCall) {
                if not belongs(call, full_path) { continue; }
                calls.append({"target": str(call.target.unparse()), "span": span(call)});
            }
            extracted.append({"path": path, "imports": imports, "symbols": symbols, "calls": calls});
        } except Exception as exc {
            extracted.append({"path": path, "error": str(exc)});
        }
    }
    references: dict = {};
    intel_error = "";
    try {
        intel = CodeIntelligence(proj_dir=repo, type_check=False);
        intel.load();
        names: set[str] = set();
        for row in extracted {
            for sym in row.get("symbols", []) {
                if sym["kind"] != "impl" and sym["kind"] != "entry_ability" and sym["name"] {
                    names.add(str(sym["name"]));
                }
            }
        }
        for name in sorted(names) {
            references[name] = [{"file": os.path.relpath(ref.file, repo),
                "line": ref.line, "column": ref.col, "role": ref.role}
                for ref in intel.references(name)];
        }
    } except Exception as exc {
        intel_error = str(exc);
    }
    with open(output_path, "w", encoding="utf-8") as f {
        f.write(json.dumps({"files": extracted, "compiler_references": references,
            "code_intelligence_error": intel_error}, ensure_ascii=False));
    }
}
