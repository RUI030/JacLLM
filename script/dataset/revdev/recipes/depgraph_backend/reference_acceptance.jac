import from graph.nodes { Package, CVE }
import from graph.snapshot_util { pkg_node_id, severity_from_cvss, build_graph_snapshot }
import from tools.risk_scorer { package_risk_score, filter_top_risk_packages }
import from walkers.remediation_walker { RemediationWalker, version_gte }


test "risk scorer weights depth, keywords, major version and directness" {
    # depth 0 (+100), "token" keyword (+50), major 0 (+40), direct (+15)
    assert package_risk_score("jsonwebtoken", "0.4.0", 0, True) == 205;
    # depth 3 -> (10 - 3) * 10, no keyword, major 3, transitive
    assert package_risk_score("left-pad", "3.0.0", 3, False) == 70;
    # depth 1 (+80), "express" keyword (+50), major 1 (+20)
    assert package_risk_score("express", "1.2.3", 1, False) == 150;

    pkgs = [
        {"key": "a", "name": "left-pad", "version": "3.0.0", "depth": 3, "is_direct": False},
        {"key": "b", "name": "jsonwebtoken", "version": "0.4.0", "depth": 0, "is_direct": True},
        {"key": "c", "name": "express", "version": "1.2.3", "depth": 1, "is_direct": False}
    ];
    edges = [
        {"from_key": "b", "to_key": "c", "required_version": "^1.2.0"},
        {"from_key": "c", "to_key": "a", "required_version": "^3.0.0"}
    ];
    kept = filter_top_risk_packages(pkgs, edges, 2);
    assert kept["truncated"] == True;
    assert kept["original_package_count"] == 3;
    kept_packages: list[dict] = kept["packages"];
    kept_edges: list[dict] = kept["edges"];
    assert [p["key"] for p in kept_packages] == ["b", "c"];
    assert len(kept_edges) == 1;
    assert kept_edges[0]["to_key"] == "c";
    assert filter_top_risk_packages(pkgs, edges)["method"] == "none";
}


test "snapshot helpers format ids and map cvss to severity" {
    assert pkg_node_id("lodash", "4.17.20") == "lodash@4.17.20";
    assert severity_from_cvss(9.8) == "CRITICAL";
    assert severity_from_cvss(7.5) == "HIGH";
    assert severity_from_cvss(5.0) == "MEDIUM";
    assert severity_from_cvss(0.1) == "LOW";
    assert severity_from_cvss(0.0) == "CLEAN";
}


test "graph snapshot scores packages and counts attached CVE nodes" {
    jwt = Package(name="revdev-jwt-auth", version="0.9.0", depth=0, is_direct=True);
    util = Package(name="revdev-util", version="2.1.0", depth=2);
    jwt ++> CVE(cve_id="CVE-REVDEV-0001", cvss_score=9.1, severity="CRITICAL");
    jwt ++> CVE(cve_id="CVE-REVDEV-0002", cvss_score=5.5);
    parsed = {
        "packages": [
            {"key": "k1", "name": "revdev-jwt-auth", "version": "0.9.0"},
            {"key": "k2", "name": "revdev-util", "version": "2.1.0"}
        ],
        "edges": [
            {"from_key": "k1", "to_key": "k2"},
            {"from_key": "k1", "to_key": "missing"}
        ]
    };
    snap = build_graph_snapshot([jwt, util], parsed, ["revdev-jwt-auth@0.9.0"]);

    snap_nodes: list[dict] = snap["nodes"];
    assert len(snap_nodes) == 2;
    first: dict = snap_nodes[0];
    assert first["id"] == "revdev-jwt-auth@0.9.0";
    assert first["cve_count"] == 2;
    assert first["cvss_score"] == 9.1;
    assert first["severity"] == "CRITICAL";
    assert first["is_spawn_root"] == True;
    assert first["risk_score"] == package_risk_score("revdev-jwt-auth", "0.9.0", 0, True);
    assert first["risk_score"] == 205;

    second: dict = snap_nodes[1];
    assert second["cve_count"] == 0;
    assert second["severity"] == "CLEAN";
    assert second["is_spawn_root"] == False;
    assert second["risk_score"] == 90;

    assert snap["edges"] == [
        {"source": "revdev-jwt-auth@0.9.0", "target": "revdev-util@2.1.0", "type": "depends_on"}
    ];
}


test "remediation walker proposes the fixed version for a vulnerable package" {
    assert version_gte("4.17.21", "4.17.21") == True;
    assert version_gte("4.18.0", "4.17.21") == True;
    assert version_gte("4.17.2", "4.17.21") == False;

    pkg = Package(name="revdev-lodash", version="4.17.15");
    pkg ++> CVE(cve_id="CVE-REVDEV-0100", cvss_score=7.4, fixed_version="4.17.21");
    w = pkg spawn RemediationWalker();

    assert len(w.reports) == 1;
    plan: dict = w.reports[0];
    assert plan["event"] == "remediation_plan";
    assert plan["package"] == "revdev-lodash";
    assert plan["from"] == "4.17.15";
    assert plan["to"] == "4.17.21";
    assert plan["status"] == "validated";
    assert plan["confidence"] == 0.9;
    assert len(w.plans) == 1;
}


test "remediation walker skips packages without a fixable CVE" {
    clean = Package(name="revdev-clean", version="1.0.0");
    w1 = clean spawn RemediationWalker();
    assert len(w1.reports) == 0;

    unfixed = Package(name="revdev-unfixed", version="1.0.0");
    unfixed ++> CVE(cve_id="CVE-REVDEV-0200", cvss_score=6.0);
    w2 = unfixed spawn RemediationWalker();
    assert len(w2.reports) == 0;
    assert w2.plans == [];
}
