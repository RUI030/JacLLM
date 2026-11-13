"""Small multi-page jac 0.34.28 web apps on the jac-shadcn template, routed with a manual <Router> as JacHammer's prompt
prescribes, and the broken or unfinished states the routing and loop-breaking rows start from.

No placement markers: the data and its helpers live in the list page's module, which its JSX makes client, so the
same code passes jac check on 0.34.28 and 0.36.1. (On 0.34.28 a separate pure data module would need `.cl.jac`:
placement does not cross modules there. 0.36 retired the marker.) The URL parameter is read as the routing guide
writes it, `params["id"]`, with an `as str` cast where a typed helper takes it.

`app(d)` renders a domain's complete app as {relative path: text}. Each was built and clicked through on 0.34.28
(list, detail by URL, unknown id, unknown address, add form), and the symptoms the start states'
requests describe were seen in the browser. `TASKS` maps a task name to a function returning the
start state and what the row has to change."""

from dataset.parser.jachammer import hunk_edits

# Domains ==================================================
# layout "outlet": a layout route renders the nav and <Outlet/>; "top": the nav sits above <Routes>.
# lookup "loop": the list module has a find function; "comp": the detail page filters with a comprehension.
DOMAINS = [
    {"key": "gear", "brand": "Outpost Gear", "one": "product", "many": "products", "Cls": "Product",
     "seg": "products", "param": "productId", "var": "product_id", "ITEMS": "PRODUCTS",
     "layout": "outlet", "lookup": "loop", "form": False,
     "items": [("trail-pack", "Trail Pack 30L", "$89", "A light daypack with a rain cover."),
               ("camp-stove", "Camp Stove", "$54", "Folds to the size of a fist."),
               ("head-lamp", "Head Lamp", "$29", "300 lumens, USB-C charging.")]},
    {"key": "team", "brand": "Northwind Team", "one": "person", "many": "people", "Cls": "Person",
     "seg": "people", "param": "handle", "var": "handle", "ITEMS": "PEOPLE",
     "layout": "top", "lookup": "comp", "form": True, "sub_label": "Role",
     "items": [("ana", "Ana Ruiz", "Design lead", "Runs the design reviews on Thursdays."),
               ("bo", "Bo Chen", "Backend engineer", "Owns the billing service."),
               ("cy", "Cy Okafor", "Support", "First reply on every ticket.")]},
    {"key": "course", "brand": "Kiln Pottery Course", "one": "lesson", "many": "lessons", "Cls": "Lesson",
     "seg": "lessons", "param": "slug", "var": "slug", "ITEMS": "LESSONS",
     "layout": "outlet", "lookup": "comp", "form": False,
     "items": [("wedging", "Wedging clay", "Week 1", "Knead out the air before you throw."),
               ("centering", "Centering", "Week 2", "Brace your elbows on your knees."),
               ("trimming", "Trimming", "Week 3", "Trim when the pot is leather-hard."),
               ("glazing", "Glazing", "Week 4", "Wax the foot before dipping.")]},
    {"key": "events", "brand": "Harbor Events", "one": "event", "many": "events", "Cls": "Event",
     "seg": "events", "param": "eventId", "var": "event_id", "ITEMS": "EVENTS",
     "layout": "top", "lookup": "loop", "form": True, "sub_label": "Date",
     "items": [("e1", "Night market", "Fri 18:00", "Food stalls along the east pier."),
               ("e2", "Harbor run", "Sat 08:00", "A 5 km loop around the marina."),
               ("e3", "Boat parade", "Sun 15:00", "Decorated boats pass the lighthouse.")]},
    {"key": "help", "brand": "Lumen Help Center", "one": "topic", "many": "topics", "Cls": "Topic",
     "seg": "topics", "param": "topicId", "var": "topic_id", "ITEMS": "TOPICS",
     "layout": "outlet", "lookup": "loop", "form": False,
     "items": [("reset-password", "Reset your password", "Account", "Use the link on the sign-in page."),
               ("export-data", "Export your data", "Privacy", "Settings, then Export, then CSV."),
               ("billing-dates", "Billing dates", "Billing", "You are billed on the day you signed up.")]},
    {"key": "issues", "brand": "Tracklet", "one": "issue", "many": "issues", "Cls": "Issue",
     "seg": "issues", "param": "issueId", "var": "issue_id", "ITEMS": "ISSUES",
     "layout": "top", "lookup": "comp", "form": True, "sub_label": "Status",
     "items": [("101", "Login button misaligned", "Open", "On small screens the button overlaps the logo."),
               ("102", "CSV export is empty", "In progress", "Exports with a date filter return no rows."),
               ("103", "Typo on pricing page", "Done", "Monthly was spelled Monthy.")]},
]


def names(d: dict) -> dict:
    """Component and file names of a domain's app."""
    c = d["Cls"]
    return {"list": f"{c}List", "detail": f"{c}Detail", "new": f"New{c}", "nav": "AppLayout" if d["layout"] == "outlet" else "NavBar",
            "find": f"find_{d['one']}", "add": f"add_{d['one']}"}


def sub(t: str, d: dict) -> str:
    """Fill @key@ placeholders (JSX braces make str.format unusable)."""
    for k, v in {**d, **names(d)}.items():
        if isinstance(v, str):
            t = t.replace(f"@{k}@", v)
    return t


# App files ================================================
def data_block(d: dict) -> str:
    """The data and its helpers, at the top of the list page's module; the other pages import them from there."""
    rows = ",\n".join(f'    {{"id": "{i}", "title": "{t}", "sub": "{s}", "body": "{b}"}}' for i, t, s, b in d["items"])
    t = "glob:pub @ITEMS@: list[dict[str, str]] = [\n" + rows + "\n];\n"
    if d["lookup"] == "loop":
        t += '''
def:pub @find@(@var@: str) -> dict[str, str] | None {
    for item in @ITEMS@ {
        if item["id"] == @var@ {
            return item;
        }
    }
    return None;
}
'''
    if d["form"]:
        t += '''
def:pub @add@(title: str, sub: str) -> str {
    new_id = "n" + str(len(@ITEMS@) + 1);
    @ITEMS@.append({"id": new_id, "title": title, "sub": sub, "body": "Added from the form."});
    return new_id;
}
'''
    return sub(t, d)


def nav(d: dict, href: bool = False) -> str:
    links = '''            <Link to="/" className="text-lg font-semibold">@brand@</Link>
            <Link to="/" className="text-sm text-muted-foreground">All @many@</Link>
'''
    if d["form"]:
        links += '            <Link to="/@seg@/new" className="text-sm text-muted-foreground">Add @one@</Link>\n'
    if d["layout"] == "outlet":
        t = '''import from "@jac/runtime" { Link, Outlet }

def:pub @nav@() -> JsxElement {
    return <div className="flex min-h-screen w-full flex-col bg-background">
        <header className="flex items-center gap-6 border-b px-6 py-4">
''' + links + '''        </header>
        <main className="mx-auto w-full max-w-3xl px-6 py-8">
            <Outlet />
        </main>
    </div>;
}
'''
    else:
        t = '''import from "@jac/runtime" { Link }

def:pub @nav@() -> JsxElement {
    return <header className="flex items-center gap-6 border-b px-6 py-4">
''' + links.replace("            <", "        <") + '''    </header>;
}
'''
    if href:
        t = a_href(t)
    return sub(t, d)


def a_href(t: str) -> str:
    """The same file with <a href> instead of <Link to> (a full page load per click)."""
    t = t.replace("<Link to=", "<a href=").replace("</Link>", "</a>")
    t = t.replace('import from "@jac/runtime" { Link, Outlet }', 'import from "@jac/runtime" { Outlet }')
    return t.replace('import from "@jac/runtime" { Link }\n', "")


def list_page(d: dict, linked: bool = True) -> str:
    title = ('<Link to={"/@seg@/" + item["id"]} className="font-medium hover:underline">{item["title"]}</Link>' if linked
             else '<span className="font-medium">{item["title"]}</span>')
    t = '''import from "@jac/runtime" { Link }
import from .ui.card { Card }

@DATA@
def:pub @list@() -> JsxElement {
    return <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">@Many@</h1>
        {[
            <Card key={item["id"]} className="p-4">
                ''' + title + '''
                <p className="text-sm text-muted-foreground">{item["sub"]}</p>
            </Card>
            for item in @ITEMS@
        ]}
    </div>;
}
'''
    if not linked:
        t = t.replace('import from "@jac/runtime" { Link }\n', "")
    return sub(t.replace("@Many@", d["many"].capitalize()).replace("@DATA@", data_block(d)), d)


def detail_page(d: dict, variant: str = "params") -> str:
    """variant "params" reads the id from the URL; "prop" takes it as a prop; "first" ignores the URL."""
    if variant == "first":
        head = '''    item = @ITEMS@[0];
'''
        imports = 'import from "@jac/runtime" { Link }\nimport from .@list@ { @ITEMS@ }\n'
        sig = "def:pub @detail@() -> JsxElement {\n"
        guard = ""
    else:
        if variant == "params":
            sig = "def:pub @detail@() -> JsxElement {\n"
            read = '''    params = useParams();
    @var@ = params["@param@"] as str;
'''
            rt = "{ Link, useParams }"
        else:
            sig = "def:pub @detail@(@var@: str) -> JsxElement {\n"
            read, rt = "", "{ Link }"
        if d["lookup"] == "loop":
            imports = f'import from "@jac/runtime" {rt}\nimport from .@list@ {{ @find@ }}\n'
            head = read + "    item = @find@(@var@);\n"
            guard = "    if not item {\n"
        else:
            imports = f'import from "@jac/runtime" {rt}\nimport from .@list@ {{ @ITEMS@ }}\n'
            head = read + '    matches = [x for x in @ITEMS@ if x["id"] == @var@];\n'
            guard = "    if not matches {\n"
        guard += '''        return <div className="flex flex-col gap-2">
            <p>No @one@ matches this address.</p>
            <Link to="/" className="text-sm underline">Back to all @many@</Link>
        </div>;
    }
'''
        if d["lookup"] == "comp":
            guard += "    item = matches[0];\n"
    t = imports + "\n" + sig + head + guard + '''    return <div className="flex flex-col gap-3">
        <Link to="/" className="text-sm text-muted-foreground">← All @many@</Link>
        <h1 className="text-2xl font-bold">{item["title"]}</h1>
        <p className="text-lg">{item["sub"]}</p>
        <p className="text-muted-foreground">{item["body"]}</p>
    </div>;
}
'''
    return sub(t, d)


def not_found(d: dict) -> str:
    return sub('''import from "@jac/runtime" { Link }

def:pub NotFound() -> JsxElement {
    return <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold">Page not found</h1>
        <p className="text-muted-foreground">Nothing lives at this address.</p>
        <Link to="/" className="underline">Go to all @many@</Link>
    </div>;
}
''', d)


def new_page(d: dict, navigates: bool = True) -> str:
    t = '''import from "@jac/runtime" { Link, useNavigate }
import from .ui.button { Button }
import from .ui.input { Input }
import from .@list@ { @add@ }

def:pub @new@() -> JsxElement {
    has title: str = "";
    has sub: str = "";
    navigate = useNavigate();

    def handle_title(e: ChangeEvent) {
        title = e.target.value;
    }
    def handle_sub(e: ChangeEvent) {
        sub = e.target.value;
    }
    def handle_submit(e: FormEvent) {
        e.preventDefault();
        if not title.strip() {
            return;
        }
        @add@(title.strip(), sub.strip());
        navigate("/");
    }

    return <form onSubmit={handle_submit} className="flex max-w-md flex-col gap-3">
        <h1 className="text-2xl font-bold">Add @one@</h1>
        <Input value={title} onChange={handle_title} placeholder="Title" />
        <Input value={sub} onChange={handle_sub} placeholder="@sub_label@" />
        <Button type="submit">Save</Button>
        <Link to="/" className="text-sm underline">Cancel</Link>
    </form>;
}
'''
    if not navigates:
        t = t.replace("{ Link, useNavigate }", "{ Link }").replace("    navigate = useNavigate();\n", "")
        t = t.replace('        navigate("/");\n', '        title = "";\n        sub = "";\n')
    return sub(t, d)


def main_jac(d: dict, detail: str = "params", catch_all: bool = True, runtime_import: bool = True,
             with_detail: bool = True) -> str:
    n = names(d)
    imports = ['import from "@jac/runtime" { Router, Routes, Route }'] if runtime_import else []
    comps = [n["nav"], n["list"]] + ([n["detail"]] if with_detail else []) + ([n["new"]] if d["form"] else []) \
        + (["NotFound"] if catch_all else [])
    imports += [f"import from .components.{c} {{ {c} }}" for c in comps]
    elem = {"params": f"<{n['detail']} />", "prop": f'<{n["detail"]} {d["var"]}={{":{d["param"]}"}} />'}[detail] \
        if detail != "first" else f"<{n['detail']} />"
    if d["layout"] == "outlet":
        ind, pre = "                ", ""
        routes = [f"<Route index={{True}} element={{<{n['list']} />}} />"]
        if d["form"]:
            routes.append(f'<Route path="{d["seg"]}/new" element={{<{n["new"]} />}} />')
        if with_detail:
            routes.append(f'<Route path="{d["seg"]}/:{d["param"]}" element={{{elem}}} />')
        if catch_all:
            routes.append('<Route path="*" element={<NotFound />} />')
        body = (f'        <Routes>\n            <Route path="/" element={{<{n["nav"]} />}}>\n'
                + "".join(ind + r + "\n" for r in routes) + "            </Route>\n        </Routes>\n")
    else:
        ind = "                "
        routes = [f'<Route path="/" element={{<{n["list"]} />}} />']
        if d["form"]:
            routes.append(f'<Route path="/{d["seg"]}/new" element={{<{n["new"]} />}} />')
        if with_detail:
            routes.append(f'<Route path="/{d["seg"]}/:{d["param"]}" element={{{elem}}} />')
        if catch_all:
            routes.append('<Route path="*" element={<NotFound />} />')
        body = (f"        <{n['nav']} />\n        <main className=\"mx-auto w-full max-w-3xl px-6 py-8\">\n"
                "            <Routes>\n" + "".join(ind + r + "\n" for r in routes) + "            </Routes>\n        </main>\n")
    return "\n".join(imports) + "\n\ndef:pub app() -> JsxElement {\n    return <Router>\n" + body + "    </Router>;\n}\n"


def app(d: dict) -> dict[str, str]:
    """The complete app: every route, linked list, detail read from the URL, a not-found page, the add form."""
    n = names(d)
    files = {"main.jac": main_jac(d), f"components/{n['nav']}.jac": nav(d), f"components/{n['list']}.jac": list_page(d),
             f"components/{n['detail']}.jac": detail_page(d), "components/NotFound.jac": not_found(d)}
    if d["form"]:
        files[f"components/{n['new']}.jac"] = new_page(d)
    return files


# Start states =============================================
# Each returns (files of the start state, the user's request). The row's changes must turn it into app(d).
def add_detail(d: dict) -> tuple[dict, str]:
    n, f = names(d), app(d)
    f["main.jac"] = main_jac(d, with_detail=False)
    f[f"components/{n['list']}.jac"] = list_page(d, linked=False)
    del f[f"components/{n['detail']}.jac"]
    return f, f"Make every {d['one']} in the list clickable, and give each one its own page at its own address so I " \
              f"can send someone a link straight to it. The page should show the {d['one']}'s details and a way back."


def literal_param(d: dict) -> tuple[dict, str]:
    n, f = names(d), app(d)
    f["main.jac"] = main_jac(d, detail="prop")
    f[f"components/{n['detail']}.jac"] = detail_page(d, "prop")
    return f, f"Whichever {d['one']} I click, the page says no {d['one']} matches this address. The list itself looks fine."


def first_item(d: dict) -> tuple[dict, str]:
    n, f = names(d), app(d)
    f[f"components/{n['detail']}.jac"] = detail_page(d, "first")
    return f, f"Every {d['one']} page shows the same {d['one']}, \"{d['items'][0][1]}\", no matter which one I open."


def links_reload(d: dict) -> tuple[dict, str]:
    n, f = names(d), app(d)
    f[f"components/{n['nav']}.jac"] = nav(d, href=True)
    f[f"components/{n['list']}.jac"] = a_href(list_page(d))
    return f, "Every click in the nav bar or the list flashes the whole page white and reloads it. It should move " \
              "between pages instantly like a normal web app."


def missing_import(d: dict) -> tuple[dict, str]:
    f = app(d)
    f["main.jac"] = main_jac(d, runtime_import=False)
    return f, "After the last change the preview only shows \"Something went wrong\" and \"Router is not defined\"."


def catch_all(d: dict) -> tuple[dict, str]:
    f = app(d)
    f["main.jac"] = main_jac(d, catch_all=False)
    del f["components/NotFound.jac"]
    return f, "If someone types an address that doesn't exist, they get an empty page. Show a proper \"page not found\" " \
              f"message with a link back to the {d['many']}."


def stay_on_form(d: dict) -> tuple[dict, str]:
    n, f = names(d), app(d)
    f[f"components/{n['new']}.jac"] = new_page(d, navigates=False)
    return f, f"When I save a new {d['one']} the form just empties and I stay there. After saving it should take me back " \
              f"to the list so I can see it."


TASKS = {"add_detail": add_detail, "literal_param": literal_param, "first_item": first_item,
         "links_reload": links_reload, "missing_import": missing_import, "catch_all": catch_all,
         "stay_on_form": stay_on_form}


# Fix steps ================================================
# A step is (tool, file or pattern, reasoning). "write" puts the file's final text; "edit" makes one edit_code per
# changed block between the file's current and final text, and takes a list of reasonings (one per edit).
def fix_steps(d: dict, task: str, rng) -> list[tuple]:
    n = names(d)
    nav, lst, det, new = (f"components/{n[k]}.jac" for k in ("nav", "list", "detail", "new"))
    route = f"{d['seg']}/:{d['param']}" if d["layout"] == "outlet" else f"/{d['seg']}/:{d['param']}"
    pick = rng.choice
    if task == "add_detail":
        return [
            ("list", "**/*.jac", pick([f"The user wants a page per {d['one']}. Looking at the project first.",
                                       "Checking which files exist before changing anything."])),
            ("read", "main.jac", "Reading main.jac to see the routes."),
            ("read", lst, pick([f"main.jac has a manual Router and no route for a single {d['one']}. Reading "
                                f"{n['list']} to see how the {d['many']} are rendered.",
                                f"No route takes an id yet. {n['list']} renders the list; reading it."])),
            ("write", det, f"The titles are plain text, no links, and each {d['one']} in {d['ITEMS']} has an `id`, "
                           f"so its address can be /{d['seg']}/<id>. {n['detail']} reads it with useParams() as "
                           f"params[\"{d['param']}\"] (subscript; the hook returns an untyped dict, hence `as str`), "
                           + (f"looks it up with {n['find']}" if d["lookup"] == "loop" else "filters " + d["ITEMS"])
                           + ", and shows a not-found message when nothing matches."),
            ("edit", "main.jac", [f"Now the route. Importing {n['detail']} in main.jac,",
                                  f"and adding path=\"{route}\". The name after the colon has to be the one "
                                  f"{n['detail']} reads, `{d['param']}`."]),
            ("edit", lst, [pick([f"Last, the links. {n['list']} needs Link from @jac/runtime,",
                                 "Importing Link in the list page,"]),
                           f"and each title becomes a <Link> to its page, which switches routes without reloading."]),
        ]
    if task == "literal_param":
        return [
            ("read", "main.jac", pick([f"The list is fine but every {d['one']} page says nothing matches, so the "
                                       f"detail page gets the wrong id. Starting at its route in main.jac.",
                                       "The detail page never finds its item. Checking what the route passes it."])),
            ("read", det, f"The route renders <{n['detail']} {d['var']}={{\":{d['param']}\"}} />. That passes the "
                          f"literal string \":{d['param']}\", never the value from the address: a path parameter only "
                          f"reaches a component through useParams(). Reading {n['detail']}."),
            ("write", det, f"{n['detail']} takes {d['var']} as a prop. It should read params[\"{d['param']}\"] from "
                           "useParams() itself; rewriting it without the prop."),
            ("edit", "main.jac", ["And the route stops passing the literal string."]),
        ]
    if task == "first_item":
        steps = [("read", "main.jac", f"Every {d['one']} page shows the first {d['one']}. Checking the route first.")]
        steps += [("read", det, f"The route has :{d['param']}, so the address carries the id. The detail page must "
                                f"be ignoring it; reading {n['detail']}.")]
        steps += [("write", det, f"{n['detail']} sets item = {d['ITEMS']}[0] and never reads the address. It should "
                                 f"take params[\"{d['param']}\"] from useParams(), look that {d['one']} up, and say so "
                                 "when nothing matches.")]
        return steps
    if task == "links_reload":
        return [
            ("grep", "<a href", "A full reload on every click means plain <a href> links: the browser requests the page "
                                "again instead of the router switching routes. Finding them."),
            ("read", nav, f"Two files. {n['nav']} first."),
            ("write", nav, "Every nav link is <a href>. Switching them to <Link to> from @jac/runtime."),
            ("read", lst, f"Now {n['list']}."),
            ("edit", lst, ["Link has to be imported here too,", "and the title link becomes <Link to>."]),
        ]
    if task == "missing_import":
        return [
            ("read", "main.jac", "\"Router is not defined\" is a runtime error: the compiled app uses Router without "
                                 "importing it. The write check does not report that (it is only a warning), so reading "
                                 "main.jac."),
            ("edit", "main.jac", ["main.jac renders <Router>, <Routes> and <Route> but never imports them. They come "
                                  "from @jac/runtime."]),
        ]
    if task == "catch_all":
        return [
            ("read", "main.jac", "Reading the routes in main.jac."),
            ("write", "components/NotFound.jac", "No route matches an unknown address, so nothing renders. Adding a "
                                                 f"NotFound component with a link back to the {d['many']}."),
            ("edit", "main.jac", ["Importing it in main.jac,",
                                  "and a path=\"*\" route, which matches any address no other route matched. It goes "
                                  "last."]),
        ]
    if task == "stay_on_form":
        return [
            ("read", new, f"Saving clears the fields but never changes the route. Reading {n['new']}."),
            ("edit", new, ["handle_submit resets the fields after saving. To leave the page it needs useNavigate "
                           "from @jac/runtime.",
                           "The hook is called once at the top of the component, not inside the handler,",
                           "and the handler navigates to the list instead of clearing the fields."]),
        ]
    raise ValueError(task)


def expand(steps: list[tuple], start: dict[str, str], final: dict[str, str]) -> list[dict]:
    """Tool calls for fix steps, with file paths under the placeholder @ROOT@. Each is {name, args, why}."""
    cur, calls = dict(start), []
    for kind, target, why in steps:
        if kind == "list":
            calls.append({"name": "list_files", "args": {"directory": "@ROOT@", "pattern": target}, "why": why})
        elif kind == "grep":
            calls.append({"name": "grep_search", "args": {"pattern": target, "path": "@ROOT@", "file_pattern": "*.jac",
                                                         "max_results": 50}, "why": why})
        elif kind == "read":
            calls.append({"name": "read_file", "args": {"file_path": f"@ROOT@/{target}", "offset": 0, "limit": 2000},
                          "why": why})
        elif kind == "write":
            calls.append({"name": "write_code", "args": {"file_path": f"@ROOT@/{target}", "content": final[target]},
                          "why": why})
            cur[target] = final[target]
        else:
            edits = hunk_edits(cur[target], final[target])
            assert len(edits) == len(why), (target, len(edits), len(why))
            for (old, new), w in zip(edits, why):
                calls.append({"name": "edit_code", "args": {"file_path": f"@ROOT@/{target}", "old_string": old,
                                                           "new_string": new, "replace_all": False}, "why": w})
            cur[target] = final[target]
    assert cur == final, [k for k in final if cur.get(k) != final[k]]
    return calls
