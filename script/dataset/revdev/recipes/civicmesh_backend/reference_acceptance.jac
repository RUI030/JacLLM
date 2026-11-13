import from main { ImpactWalker, PathfinderWalker }
import from graph.nodes { PersonNode, NeedNode, ResourceNode, ApplicationNode }
import from graph.edges { has_need, applied_to, leads_to }


# ---- ImpactWalker: per-person aggregation over has_need ----

test "impact aggregates languages and need categories across people" {
    p1 = PersonNode(user_id="revdev-impact-u1", language="xq");
    p2 = PersonNode(user_id="revdev-impact-u2", language="xq");
    root ++> p1;
    root ++> p2;
    p1 +>: has_need() :+> NeedNode(category="revdev-impact-cat", urgency="immediate");
    p2 +>: has_need() :+> NeedNode(category="revdev-impact-cat");

    w = root spawn ImpactWalker();
    assert len(w.reports) == 1;
    out = w.reports[0];
    assert out["total_users"] >= 2;

    langs = {str(pair["lang"]): int(pair["count"]) for pair in out["languages"]};
    assert langs["xq"] == 2;
    cats = {str(pair["category"]): int(pair["count"]) for pair in out["need_categories"]};
    assert cats["revdev-impact-cat"] == 2;
    assert w.summary == out;
}


# ---- ImpactWalker: applications over applied_to ----

test "impact counts applications, skips archived ones and ranks resources" {
    p = PersonNode(user_id="revdev-impact-apps", language="en");
    root ++> p;
    for s in ["approved", "approved", "denied", "applied", "pending"] {
        p +>: applied_to() :+> ApplicationNode(status=s, resource_name="RevDev Unique Agency");
    }
    p +>: applied_to() :+> ApplicationNode(status="archived", resource_name="RevDev Unique Agency");

    w = root spawn ImpactWalker();
    out = w.reports[0];
    assert out["total_applications"] >= 5;
    counts = out["app_status_counts"];
    assert counts["approved"] >= 2;
    assert counts["denied"] >= 1;
    assert "archived" not in counts;
    assert 0 <= out["approval_rate"] and out["approval_rate"] <= 100;

    top = {str(r["name"]): int(r["count"]) for r in out["top_resources"]};
    assert top["RevDev Unique Agency"] == 5;
}


# ---- PathfinderWalker: BFS over leads_to edges ----

test "pathfinder finds a two-hop escape path over leads_to" {
    a = ResourceNode(agency_name="RevDev Shelter", category="revdev-path-one");
    b = ResourceNode(agency_name="RevDev Transitional", category="revdev-path-one");
    c = ResourceNode(agency_name="RevDev Voucher", category="revdev-path-one");
    root ++> a;
    root ++> b;
    root ++> c;
    a +>: leads_to(transition_reason="intake opens case", typical_days=10, difficulty="easy") :+> b;
    b +>: leads_to(transition_reason="priority bump", typical_days=20, difficulty="hard") :+> c;

    w = root spawn PathfinderWalker(start_category="revdev-path-one");
    assert len(w.reports) == 1;
    out = w.reports[0];
    assert out["ok"] == True;
    assert out["path_count"] == 1;
    path = out["paths"][0];
    assert path["start"] == "RevDev Shelter";
    assert path["end"] == "RevDev Voucher";
    assert path["hop_count"] == 2;
    assert len(path["hops"]) == 2;
    assert path["hops"][0]["from"] == "RevDev Shelter";
    assert path["hops"][0]["to"] == "RevDev Transitional";
    assert path["hops"][1]["to"] == "RevDev Voucher";
}


test "pathfinder collects one path per chain and honours max_paths" {
    x = ResourceNode(agency_name="RevDev Chain1 A", category="revdev-path-two");
    y = ResourceNode(agency_name="RevDev Chain1 B", category="revdev-path-two");
    z = ResourceNode(agency_name="RevDev Chain1 C", category="revdev-path-two");
    p = ResourceNode(agency_name="RevDev Chain2 A", category="revdev-path-two");
    q = ResourceNode(agency_name="RevDev Chain2 B", category="revdev-path-two");
    r = ResourceNode(agency_name="RevDev Chain2 C", category="revdev-path-two");
    for n in [x, y, z, p, q, r] {
        root ++> n;
    }
    x +>: leads_to() :+> y;
    y +>: leads_to() :+> z;
    p +>: leads_to() :+> q;
    q +>: leads_to() :+> r;

    w = root spawn PathfinderWalker(start_category="revdev-path-two");
    out = w.reports[0];
    assert out["path_count"] == 2;
    ends = sorted([str(pp["start"]) + "->" + str(pp["end"]) for pp in out["paths"]]);
    assert ends == ["RevDev Chain1 A->RevDev Chain1 C", "RevDev Chain2 A->RevDev Chain2 C"];
    assert w.summary["path_count"] == 2;

    capped = root spawn PathfinderWalker(start_category="revdev-path-two", max_paths=1);
    assert capped.reports[0]["path_count"] == 1;
    assert len(capped.reports[0]["paths"]) == 1;
}


test "pathfinder reports no paths when resources have no transitions" {
    root ++> ResourceNode(agency_name="RevDev Lonely", category="revdev-path-none");
    w = root spawn PathfinderWalker(start_category="revdev-path-none");
    out = w.reports[0];
    assert out["ok"] == True;
    assert out["start_category"] == "revdev-path-none";
    assert out["max_hops"] == 3;
    assert out["path_count"] == 0;
    assert out["paths"] == [];
}
