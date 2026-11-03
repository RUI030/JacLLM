import os;
import json;
import from jaclang.byllm.lib { MockLLM }

# tools.jac picks its model when imported; give it a placeholder key so the
# selection succeeds. No real model is ever called: every test swaps in MockLLM.
with entry {
    os.environ.setdefault("OPENAI_API_KEY", "revdev-mock-key");
}

import tools as t;
import from models { DenialReason, AppealStrength, PolicyClause, Contradiction, AppealLetter, Claim, Policy, Appeal }
import from tools {
    extract_denial_reason,
    extract_relevant_clauses,
    find_contradictions,
    assess_appeal_strength,
    draft_appeal_letter
}
import from main { submit_claim, list_appeals }


def mock(outputs: list) {
    t.llm = MockLLM(model_name="mockllm", config={"outputs": outputs});
}


test "classification tools normalise free-text model answers into enums" {
    mock([
        "  prior_auth was not obtained ",
        "The denial says EXPERIMENTAL procedure",
        "no idea",
        "Very Strong",
        "strong",
        "weak case",
        "unclear"
    ]);
    assert extract_denial_reason("d1") == DenialReason.PRIOR_AUTH_MISSING;
    assert extract_denial_reason("d2") == DenialReason.EXPERIMENTAL_OR_INVESTIGATIONAL;
    assert extract_denial_reason("d3") == DenialReason.OTHER;
    assert assess_appeal_strength([]) == AppealStrength.VERY_STRONG;
    assert assess_appeal_strength([]) == AppealStrength.STRONG;
    assert assess_appeal_strength([]) == AppealStrength.WEAK;
    assert assess_appeal_strength([]) == AppealStrength.MODERATE;
}


test "list tools parse fenced or prose-wrapped JSON and skip non-objects" {
    mock([
        "Here you go:\n```json\n[{\"section\": \"7.2(i)\", \"title\": \"Sleep studies\", \"text\": \"Covered when indicated.\"}, \"junk\", 5]\n```",
        "Found: [{\"denial_quote\": \"not necessary\", \"policy_quote\": \"covered\", \"clause_section\": \"7.2(i)\", \"explanation\": \"conflict\"}] end",
        "no json here"
    ]);
    clauses = extract_relevant_clauses("policy", DenialReason.NOT_MEDICALLY_NECESSARY);
    assert len(clauses) == 1;
    assert isinstance(clauses[0], PolicyClause);
    assert clauses[0].section == "7.2(i)";
    assert clauses[0].title == "Sleep studies";
    assert clauses[0].text == "Covered when indicated.";
    assert clauses[0].relevance_note == "";

    found = find_contradictions("denial", "record", clauses);
    assert len(found) == 1;
    assert isinstance(found[0], Contradiction);
    assert found[0].clause_section == "7.2(i)";
    assert found[0].explanation == "conflict";

    assert find_contradictions("denial", "record", clauses) == [];
}


test "draft_appeal_letter rehydrates an AppealLetter and coerces citations" {
    mock([
        "Sure! {\"subject\": \"Appeal of claim C-1\", \"salutation\": \"Dear Appeals Team,\", \"body\": \"Please reverse {the} denial.\", \"citations\": \"Plan Section 7.2(i)\", \"closing\": \"Sincerely, Pat\"} thanks",
        "not json at all"
    ]);
    letter = draft_appeal_letter(
        patient_name="Pat", member_id="M-1", claim_number="C-1",
        date_of_service="2026-04-18", cpt_code="95810", billed_amount=10.0,
        plan_name="Gold", denial_reason=DenialReason.OTHER,
        contradictions=[], clinical_record=""
    );
    assert isinstance(letter, AppealLetter);
    assert letter.subject == "Appeal of claim C-1";
    assert letter.salutation == "Dear Appeals Team,";
    assert letter.body == "Please reverse {the} denial.";
    assert letter.citations == ["Plan Section 7.2(i)"];
    assert letter.closing == "Sincerely, Pat";

    empty = draft_appeal_letter(
        patient_name="Pat", member_id="M-1", claim_number="C-1",
        date_of_service="2026-04-18", cpt_code="95810", billed_amount=10.0,
        plan_name="Gold", denial_reason=DenialReason.OTHER,
        contradictions=[], clinical_record=""
    );
    assert empty.subject == "";
    assert empty.body == "";
    assert empty.citations == [];
}


test "submit_claim runs the five tools and persists Claim, Policy and Appeal" {
    mock([
        "OUT_OF_NETWORK",
        "[{\"section\": \"4.1\", \"title\": \"Network\", \"text\": \"Emergency care is in-network.\", \"relevance_note\": \"ER visit\"}]",
        "[{\"denial_quote\": \"provider out of network\", \"policy_quote\": \"Emergency care is in-network.\", \"clause_section\": \"4.1\", \"explanation\": \"ER exception applies\"}]",
        "STRONG",
        "{\"subject\": \"Appeal RVD-SUB-1\", \"salutation\": \"Dear Sir,\", \"body\": \"Body text.\", \"citations\": [\"Plan Section 4.1\", \"ER note\"], \"closing\": \"Regards\"}"
    ]);
    w = root spawn submit_claim(
        patient_name="Alex Kim", member_id="RVD-MEM-1", claim_number="RVD-SUB-1",
        date_of_service="2026-05-01", cpt_code="99285", billed_amount=1200.5,
        plan_name="Silver PPO", denial_text="provider out of network",
        policy_text="4.1 Emergency care is in-network.", clinical_record="ER visit"
    );
    assert len(w.reports) == 1;
    r = w.reports[0];
    assert set(r.keys()) == {"appeal_id", "claim_id", "subject", "letter", "citations"};
    assert r["claim_id"] == "RVD-SUB-1";
    assert r["subject"] == "Appeal RVD-SUB-1";
    assert r["letter"] == "Dear Sir,\n\nBody text.\n\nRegards";
    assert r["citations"] == ["Plan Section 4.1", "ER note"];
    assert r["appeal_id"].startswith("APL-");
    assert len(r["appeal_id"]) == 12;

    claims = [c for c in [root -->][?:Claim] if c.claim_id == "RVD-SUB-1"];
    assert len(claims) == 1;
    assert claims[0].billed_amount == 1200.5;
    assert claims[0].clinical_record == "ER visit";
    policies = [p for p in [root -->][?:Policy] if p.policy_id == "POL-RVD-MEM-1"];
    assert len(policies) == 1;
    assert policies[0].plan_name == "Silver PPO";

    appeals = [a for a in [root -->][?:Appeal] if a.claim_id == "RVD-SUB-1"];
    assert len(appeals) == 1;
    a = appeals[0];
    assert a.appeal_id == r["appeal_id"];
    assert a.policy_id == "POL-RVD-MEM-1";
    assert a.denial_reason == DenialReason.OUT_OF_NETWORK;
    assert a.strength == AppealStrength.STRONG;
    assert a.letter_subject == "Appeal RVD-SUB-1";
    assert json.loads(a.contradictions_json) == [{
        "denial_quote": "provider out of network",
        "policy_quote": "Emergency care is in-network.",
        "clause_section": "4.1",
        "explanation": "ER exception applies"
    }];
    assert json.loads(a.citations_json) == ["Plan Section 4.1", "ER note"];
    assert a.created_at != "";
}


test "list_appeals reports summary rows including an appeal with no contradictions" {
    mock(["CODING_ERROR", "[]", "[]", "WEAK", "model refused"]);
    w = root spawn submit_claim(
        patient_name="Sam Lee", member_id="RVD-MEM-2", claim_number="RVD-LIST-2",
        date_of_service="2026-05-02", cpt_code="12345", billed_amount=50.0,
        plan_name="Bronze", denial_text="wrong code", policy_text="policy"
    );
    r = w.reports[0];
    assert r["subject"] == "";
    assert r["letter"] == "\n\n\n\n";
    assert r["citations"] == [];

    appeals = [a for a in [root -->][?:Appeal] if a.claim_id == "RVD-LIST-2"];
    assert len(appeals) == 1;
    assert appeals[0].denial_reason == DenialReason.CODING_ERROR;
    assert appeals[0].strength == AppealStrength.WEAK;
    assert appeals[0].contradictions_json == "[]";
    assert appeals[0].citations_json == "[]";

    lw = root spawn list_appeals();
    assert len(lw.reports) == 1;
    rows = lw.reports[0];
    assert len(rows) >= 1;
    mine = [row for row in rows if row["claim_id"] == "RVD-LIST-2"];
    assert len(mine) == 1;
    assert set(mine[0].keys()) == {"appeal_id", "claim_id", "subject", "created_at"};
    assert mine[0]["appeal_id"] == r["appeal_id"];
    assert mine[0]["subject"] == "";
}
