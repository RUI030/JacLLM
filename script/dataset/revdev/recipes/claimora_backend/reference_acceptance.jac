import from main { ingest_documents, get_scores, get_evidence, get_timeline, reset_case }
import from nodes.data_nodes {
    DocumentNode,
    EvidenceNode,
    TimelineNode,
    FalsityNode,
    ScientorNode,
    MaterialityNode,
    CausationNode
}


test "ingest_documents attaches one DocumentNode per uploaded file" {
    root spawn ingest_documents(
        files=[
            {"filename": "revdev-claim-a.txt", "content": "Billing record A", "doc_type": "invoice"},
            {"filename": "revdev-claim-b.txt", "content": "Email thread B", "doc_type": "email"}
        ]
    );
    docs = [root -->][?:DocumentNode];
    a = [d for d in docs if d.filename == "revdev-claim-a.txt"];
    b = [d for d in docs if d.filename == "revdev-claim-b.txt"];
    assert len(a) >= 1;
    assert len(b) >= 1;
    assert a[0].content == "Billing record A";
    assert a[0].doc_type == "invoice";
    assert b[0].doc_type == "email";
}


test "ingest_documents truncates long content to 6000 characters" {
    long_text = "x" * 6500;
    root spawn ingest_documents(
        files=[{"filename": "revdev-claim-long.txt", "content": long_text, "doc_type": "report"}]
    );
    docs = [d for d in [root -->][?:DocumentNode] if d.filename == "revdev-claim-long.txt"];
    assert len(docs) >= 1;
    assert len(docs[0].content) == 6000;
    assert docs[0].doc_type == "report";
}


test "get_evidence and get_timeline report graph nodes as dictionaries" {
    root ++> EvidenceNode(
        evidence_type="revdev-upcoding",
        description="Claims billed at a higher level than documented",
        source_doc="revdev-claim-a.txt",
        confidence=0.85
    );
    root ++> TimelineNode(
        events=["revdev-first-claim", "revdev-audit"],
        fraud_start="2019-01",
        fraud_end="2021-06",
        total_duration_months=29
    );
    ev = root spawn get_evidence();
    mine = [r for r in ev.reports if r["type"] == "revdev-upcoding"];
    assert len(mine) >= 1;
    assert mine[0]["source"] == "revdev-claim-a.txt";
    assert mine[0]["confidence"] == 0.85;
    assert mine[0]["description"] == "Claims billed at a higher level than documented";

    tl = root spawn get_timeline();
    found = [r for r in tl.reports if r["events"] == ["revdev-first-claim", "revdev-audit"]];
    assert len(found) >= 1;
    assert found[0]["fraud_start"] == "2019-01";
    assert found[0]["total_duration_months"] == 29;
}


test "reset_case removes ingested documents and evidence" {
    root spawn ingest_documents(
        files=[{"filename": "revdev-claim-reset.txt", "content": "to be cleared", "doc_type": "memo"}]
    );
    root ++> EvidenceNode(evidence_type="revdev-reset-ev", description="temp", source_doc="revdev-claim-reset.txt", confidence=0.5);
    assert len([d for d in [root -->][?:DocumentNode] if d.filename == "revdev-claim-reset.txt"]) >= 1;

    w = root spawn reset_case();
    assert w.reports == ["Case reset complete"];
    assert len([root -->][?:DocumentNode]) == 0;
    assert len([root -->][?:EvidenceNode]) == 0;
    ev = root spawn get_evidence();
    assert len(ev.reports) == 0;
}


test "get_scores reports each FCA element strength with zero defaults" {
    root spawn reset_case();
    root ++> FalsityNode(falsity_type="revdev-false-cert", strength_score=0.73);
    root ++> ScientorNode(knowledge_type="revdev-reckless", strength_score=0.41);
    root ++> MaterialityNode(government_relied=True, strength_score=0.9);
    w = root spawn get_scores();
    assert len(w.reports) == 1;
    scores = w.reports[0];
    assert scores["falsity"] == 0.73;
    assert scores["scienter"] == 0.41;
    assert scores["materiality"] == 0.9;
    assert scores["causation"] == 0.0;
}
