import from models.codes { DiagnosisCode }
import from models.provider { ProviderOption }
import from models.session { UserSession, append_message, update_session_timestamp, session_to_dict }
import from services.common { APP_DISCLAIMER }
import from services.pdf_exporter { build_session_pdf_payload }


def make_session(sid: str) -> UserSession {
    return UserSession(
        session_id=sid,
        created_at="2026-04-05T07:23:04.356057+00:00",
        updated_at="2026-04-05T07:23:04.356057+00:00"
    );
}


test "append_message and timestamp update mutate the session transcript" {
    s = make_session("revdev-ca-msg-0001");
    append_message(s, "user", "I have a headache", "Conversation Agent", "2026-04-05T07:24:10+00:00");
    append_message(s, "assistant", "How long has it lasted?", "Conversation Agent", "2026-04-05T07:24:12+00:00");
    update_session_timestamp(s, "2026-04-05T07:30:00+00:00");
    assert len(s.transcript) == 2;
    assert s.transcript[0].role == "user";
    assert s.transcript[1].content == "How long has it lasted?";
    assert s.updated_at == "2026-04-05T07:30:00+00:00";
    assert s.created_at == "2026-04-05T07:23:04.356057+00:00";
}


test "session_to_dict serializes codes, providers and agent trace" {
    s = make_session("revdev-ca-dict-0002");
    s.location = "Ann Arbor, MI";
    s.assigned_codes = [DiagnosisCode(code="R51.9", description="Headache, unspecified", category="Neurological", confidence=0.8)];
    s.provider_options = [
        ProviderOption(name="Dr. Revdev", specialty="Neurology", address="1 Main St, Ann Arbor", phone="555-0100", accepts_insurance=["Aetna"])
    ];
    s.agent_path = ["Diagnosis Agent:done", "Calling Agent:active", "noise"];
    append_message(s, "user", "hello", "Conversation Agent", "2026-04-05T07:24:10+00:00");
    d = session_to_dict(s);
    assert d["session_id"] == "revdev-ca-dict-0002";
    assert d["location"] == "Ann Arbor, MI";
    assert d["assigned_codes"][0]["code"] == "R51.9";
    assert d["assigned_codes"][0]["source"] == "symptom_mapper";
    assert d["provider_options"][0]["name"] == "Dr. Revdev";
    assert d["provider_options"][0]["accepting_new_patients"] == True;
    assert d["provider_options"][0]["telehealth_available"] == False;
    assert d["transcript"][0] == {"role": "user", "content": "hello", "timestamp": "2026-04-05T07:24:10+00:00", "agent": "Conversation Agent"};
    statuses = {item["name"]: item["status"] for item in d["agent_trace"]};
    assert len(d["agent_trace"]) == 6;
    assert statuses["Diagnosis Agent"] == "done";
    assert statuses["Calling Agent"] == "active";
    assert statuses["Intervention Agent"] == "listening";
    assert statuses["Summary Agent"] == "idle";
    assert d["disclaimer"] == APP_DISCLAIMER;
}


test "pdf payload metadata uses the session id and shared disclaimer" {
    s = make_session("revdev-ca-pdf-0003");
    p = build_session_pdf_payload(s);
    assert p["file_name"] == "anchorcare_session_revdev-ca-pdf-0003.pdf";
    assert p["mime_type"] == "application/pdf";
    assert p["session_id"] == "revdev-ca-pdf-0003";
    assert p["disclaimer"] == APP_DISCLAIMER;
    assert isinstance(p["generated_at"], str) and "T" in p["generated_at"];
    html = p["html_content"];
    assert "Session ID: </span>revdev-ca-pdf-0003" in html;
    assert "2026-04-05 at 07:23 UTC" in html;
    assert "No patient-reported symptoms captured." in html;
    assert "No provisional diagnosis outputs recorded." in html;
    assert "No provider recommendations available yet." in html;
    assert "No conversation transcript available." in html;
    assert "No patient information recorded." in html;
    assert "No active safety flags recorded." in html;
}


test "pdf html renders symptoms, codes, providers and transcript with escaping" {
    s = make_session("revdev-ca-pdf-0004");
    s.extracted_symptoms = ["chest pain", "<dizzy>"];
    s.insurance = "Aetna";
    s.risk_flags = ["self-harm"];
    s.assigned_codes = [DiagnosisCode(code="R07.9", description="Chest pain, unspecified", category="Cardio", confidence=0.7)];
    s.provider_options = [
        ProviderOption(name="Heart & Co", specialty="Cardiology", address="2 Elm St", phone="555-0200", accepts_insurance=["Aetna"], notes="Walk-ins")
    ];
    append_message(s, "user", "My chest hurts", "Conversation Agent", "2026-04-05T09:15:00+00:00");
    append_message(s, "assistant", "Noted.", "Diagnosis Agent", "2026-04-05T09:16:00+00:00");
    html = build_session_pdf_payload(s)["html_content"];
    assert "The patient reported: chest pain, &lt;dizzy&gt;." in html;
    assert "Top provisional match: R07.9 — Chest pain, unspecified." in html;
    assert "1 provider recommendation(s) available." in html;
    assert "Safety review flagged: self-harm." in html;
    assert '<span class="code-id">R07.9</span>' in html;
    assert '<p class="provider-name">Heart &amp; Co</p>' in html;
    assert "Insurance: </span>Aetna" in html;
    assert '<li class="flag-item">self-harm</li>' in html;
    assert '<p class="msg-header-patient">Patient · 09:15</p>' in html;
    assert '<p class="msg-header">Diagnosis Agent · 09:16</p>' in html;
}


test "explicit summary text replaces the generated clinical summary" {
    s = make_session("revdev-ca-pdf-0005");
    s.summary_text = "  Follow up with <GP> soon.  ";
    s.extracted_symptoms = ["cough"];
    html = build_session_pdf_payload(s)["html_content"];
    assert "<h2>Clinical Summary</h2><p>Follow up with &lt;GP&gt; soon.</p>" in html;
    assert "The patient reported:" not in html;
}
