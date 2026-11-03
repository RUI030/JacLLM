import from main { TimelineEntry, person_timeline, plain_status, log_activity }
import from graph.nodes { Incident, Person, Source, Claim, Alert, Subscription, InvestigationRun, ActivityEntry }
import from graph.edges { Involves, Asserts, About, HasSubscription, Receives, HasInvestigation }


# Build an incident with one involved person and one source on root.
def make_case(tag: str) -> tuple {
    incident = Incident(name="Revdev incident " + tag);
    person = Person(name="Revdev person " + tag);
    source = Source(name="Revdev source " + tag);
    root ++> incident;
    root ++> source;
    incident +>:Involves():+> person;
    return (incident, person, source);
}

def add_claim(incident: Incident, person: Person, source: Source, status: str,
    reported: str, reference: str) -> Claim {
    claim = Claim(claim_type=status, value="Statement " + reference,
        timestamp=reported, ingested_at="2026-09-20T12:00:00Z",
        source_reference=reference, incident_id=jid(incident));
    source +>:Asserts():+> claim;
    claim +>:About():+> person;
    return claim;
}


test "timeline orders cited claims and marks status changes" {
    fx = make_case("tl-claims");
    incident = fx[0];
    person = fx[1];
    source = fx[2];
    later = add_claim(incident, person, source, "FOUND_SAFE", "2026-09-20T10:00:00Z", "REF-TL-2");
    earlier = add_claim(incident, person, source, "MISSING", "2026-09-20T08:00:00Z", "REF-TL-1");
    rows = person_timeline(jid(incident), jid(person));
    assert len(rows) == 2;
    assert all(isinstance(r, TimelineEntry) for r in rows);
    assert [r.claim_type for r in rows] == ["MISSING", "FOUND_SAFE"];
    assert rows[0].claim_id == jid(earlier) and not rows[0].status_changed;
    assert rows[1].claim_id == jid(later);
    assert rows[1].status_changed and rows[1].previous_claim_id == jid(earlier);
    assert rows[1].previous_claim_type == "MISSING";
    assert rows[0].source_name == "Revdev source tl-claims";
    assert rows[0].source_ids == [jid(source)];
    assert rows[0].source_reference == "REF-TL-1";
    assert all(r.total_entries == 2 for r in rows);
}


test "timeline includes subscription alerts and investigation runs" {
    fx = make_case("tl-linked");
    incident = fx[0];
    person = fx[1];
    source = fx[2];
    claim = add_claim(incident, person, source, "INJURED", "2026-09-21T08:00:00Z", "REF-LINK-1");
    sub = Subscription(subscriber_name="Revdev subscriber");
    person +>:HasSubscription():+> sub;
    sub +>:Receives():+> Alert(message="Status update", created_at="2026-09-21T09:00:00Z",
        severity="warning", claim_id=jid(claim));
    run = InvestigationRun(person_id=jid(person), fingerprint="fp-linked",
        result_json='{"status": "DONE", "message": "Cited report", "citations": [{"claim_id": "' + jid(claim) + '"}]}',
        created_at="2026-09-21T10:00:00Z", mode="LIVE");
    incident +>:HasInvestigation():+> run;
    rows = person_timeline(jid(incident), jid(person));
    assert [r.kind for r in rows] == ["claim", "alert", "investigation"];
    alert_row = rows[1];
    assert alert_row.claim_id == jid(claim);
    assert alert_row.subscriber_names == ["Revdev subscriber"];
    assert alert_row.status == "warning" and alert_row.text == "Status update";
    run_row = rows[2];
    assert run_row.id == jid(run) and run_row.mode == "LIVE";
    assert run_row.status == "DONE" and run_row.text == "Cited report";
    assert run_row.claim_id == jid(claim);
    assert all(r.total_entries == 3 for r in rows);
}


test "timeline excludes other incidents and unknown ids" {
    fx = make_case("tl-scope");
    incident = fx[0];
    person = fx[1];
    source = fx[2];
    add_claim(incident, person, source, "MISSING", "2026-09-22T08:00:00Z", "REF-SCOPE-1");
    other = Claim(claim_type="FOUND_SAFE", value="Other incident", timestamp="2026-09-22T09:00:00Z",
        incident_id="some-other-incident");
    source +>:Asserts():+> other;
    other +>:About():+> person;
    rows = person_timeline(jid(incident), jid(person));
    assert len(rows) == 1;
    assert rows[0].source_reference == "REF-SCOPE-1";
    assert person_timeline("00000000-0000-0000-0000-000000000000", jid(person)) == [];
    assert person_timeline(jid(incident), "00000000-0000-0000-0000-000000000000") == [];
}


test "plain status turns claim codes into words" {
    assert plain_status("MISSING") == "reported missing";
    assert plain_status("FOUND_SAFE") == "reported safe";
    assert plain_status("SHELTER_CHECK_IN") == "shelter check in";
}


test "log activity attaches an activity entry to root" {
    log_activity("RevdevWalker", "Revdev activity message", "revdev-incident-42");
    entries = [e for e in [root -->][?:ActivityEntry] if e.message == "Revdev activity message"];
    assert len(entries) >= 1;
    entry = entries[0];
    assert entry.walker_name == "RevdevWalker";
    assert entry.incident_id == "revdev-incident-42";
    assert entry.created_at != "";
}
