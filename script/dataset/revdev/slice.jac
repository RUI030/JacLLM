"""Extract top-level compiler AST declarations for verified module tasks."""
import json;
import sys;
import from pathlib { Path }
import from jaclang.jac0core.program { JacProgram }
import jaclang.jac0core.unitree as uni;

with entry {
    request = json.loads(Path(sys.argv[1]).read_text());
    result: list = [];
    for path in request["files"] {
        source = Path(path).read_text();
        mod = JacProgram().parse_str(source, path);
        items: list = [];
        for item in mod.body {
            names: list[str] = [];
            if isinstance(item, uni.Ability) {
                names.append(str(item.name_ref.value));
            } elif isinstance(item, uni.Archetype) or isinstance(item, uni.Enum) {
                names.append(str(item.name.value));
            }
            items.append({"kind": type(item).__name__, "names": names,
                "code": item.unparse(), "line": item.loc.first_line,
                "end_line": item.loc.last_line});
        }
        result.append({"file": path, "items": items});
    }
    Path(sys.argv[2]).write_text(json.dumps(result));
}
