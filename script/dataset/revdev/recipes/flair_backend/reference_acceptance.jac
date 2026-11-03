import from jaclang.byllm.lib { MockLLM }
import services.llm as llm_mod;
import from services.models { DeterministicSignal, LlmFindingDraft, LlmAuditBundle }
import from services.audits {
    safe_retention_bundle,
    parse_llm_bundle,
    fallback_bundle,
    rubric_overall,
    blended_score,
}


def make_signal(lane: str, category: str, severity: str) -> DeterministicSignal {
    return DeterministicSignal(
        lane_retention_or_conversion=lane,
        category=category,
        severity=severity,
        confidence=0.8,
        page_url="https://example.test/" + category,
        recommendation="Fix " + category,
    );
}


test "safe_retention_bundle parses fenced LLM JSON and clamps values" {
    llm_mod.llm = MockLLM(
        model_name="mockllm",
        config={
            "outputs": [
                "```json\n{\"score\": 140, \"onboarding_activation\": 12, \"habit_loop_strength\": -3, \"dark_pattern_risk_score\": 4, \"strengths\": [\"clear hero\", 7], \"findings\": [{\"category\": \"cue design\", \"lane_retention_or_conversion\": \"conversion\", \"confidence\": 1.7, \"page_url\": \"https://app.test/home\", \"legal_safe\": false}]}\n```"
            ]
        },
    );
    signals = [make_signal("retention", "streak pressure", "high")];
    bundle = safe_retention_bundle("https://app.test", "evidence text", signals, 55);
    assert isinstance(bundle, LlmAuditBundle);
    assert bundle.score == 100;
    assert bundle.onboarding_activation == 10;
    assert bundle.habit_loop_strength == 0;
    assert bundle.reward_design_feedback == 5;
    assert bundle.trust_emotional_safety == 5;
    assert bundle.dark_pattern_risk_score == 4;
    assert bundle.strengths == ["clear hero", "7"];
    assert bundle.weaknesses == [];
    assert len(bundle.findings) == 1;
    f = bundle.findings[0];
    assert f.category == "cue design";
    assert f.lane_retention_or_conversion == "retention";
    assert f.confidence == 1.0;
    assert f.severity == "medium";
    assert f.page_url == "https://app.test/home";
    assert f.primary_metric == "repeat sessions";
    assert f.guardrail_metric == "complaints and opt-outs";
    assert f.legal_safe == False;
}


test "safe_retention_bundle falls back to retention signals when LLM gives no findings" {
    llm_mod.llm = MockLLM(
        model_name="mockllm",
        config={"outputs": ["{\"score\": 90, \"findings\": []}"]},
    );
    signals = [
        make_signal("retention", "reward feedback", "high"),
        make_signal("conversion", "pricing clarity", "low"),
        make_signal("retention", "stopping cues", "low"),
    ];
    bundle = safe_retention_bundle("https://fallback.test", "pack", signals, 82);
    assert bundle.score == 82;
    assert bundle.habit_loop_strength == 7;
    assert bundle.trust_emotional_safety == 7;
    assert bundle.dark_pattern_risk_score == 0;
    assert len(bundle.findings) == 2;
    assert [f.category for f in bundle.findings] == ["reward feedback", "stopping cues"];
    assert bundle.findings[0].severity == "high";
    assert bundle.findings[0].recommendation == "Fix reward feedback";
    assert all(f.legal_safe for f in bundle.findings);
    assert len(bundle.weaknesses) == 1;
}


test "safe_retention_bundle survives unparsable LLM output with a baseline finding" {
    llm_mod.llm = MockLLM(
        model_name="mockllm",
        config={"outputs": ["the model rambled without any json"]},
    );
    signals = [make_signal("conversion", "checkout friction", "medium")];
    bundle = safe_retention_bundle("https://broken.test", "pack", signals, 30);
    assert bundle.score == 30;
    assert bundle.onboarding_activation == 3;
    assert bundle.friction_reduction == 3;
    assert len(bundle.findings) == 1;
    base = bundle.findings[0];
    assert base.category == "baseline opportunity";
    assert base.lane_retention_or_conversion == "retention";
    assert base.severity == "medium";
    assert base.confidence == 0.55;
    assert base.primary_metric == "retention score";
    assert base.legal_safe == True;
}


test "parse_llm_bundle and fallback_bundle work without a model" {
    parsed = parse_llm_bundle(
        "Here you go: {\"score\": 47, \"friction_reduction\": 8, \"findings\": [{\"category\": \"onboarding friction\", \"severity\": \"critical\", \"confidence\": -0.4}]} thanks",
        [],
        10,
    );
    assert parsed.score == 47;
    assert parsed.friction_reduction == 8;
    assert parsed.findings[0].severity == "critical";
    assert parsed.findings[0].confidence == 0.0;
    mid = fallback_bundle("conversion", [make_signal("conversion", "cta clarity", "low")], 60);
    assert mid.progression_investment == 5;
    assert len(mid.findings) == 1;
    assert mid.findings[0].lane_retention_or_conversion == "conversion";
    assert mid.findings[0].category == "cta clarity";
}


test "rubric_overall weights category scores and blended_score averages" {
    all_ten = LlmAuditBundle(
        onboarding_activation=10, habit_loop_strength=10, reward_design_feedback=10,
        social_retention_mechanics=10, attention_capture_session_depth=10,
        personalization_adaptation=10, friction_reduction=10, progression_investment=10,
        reentry_notification_systems=10, trust_emotional_safety=10,
    );
    assert rubric_overall(all_ten) == 100;
    zero = LlmAuditBundle(
        onboarding_activation=0, habit_loop_strength=0, reward_design_feedback=0,
        social_retention_mechanics=0, attention_capture_session_depth=0,
        personalization_adaptation=0, friction_reduction=0, progression_investment=0,
        reentry_notification_systems=0, trust_emotional_safety=-4,
    );
    assert rubric_overall(zero) == 0;
    mixed = LlmAuditBundle(
        onboarding_activation=10, habit_loop_strength=0, reward_design_feedback=0,
        social_retention_mechanics=0, attention_capture_session_depth=0,
        personalization_adaptation=15, friction_reduction=0, progression_investment=0,
        reentry_notification_systems=0, trust_emotional_safety=0,
    );
    assert rubric_overall(mixed) == 20;
    assert blended_score(80, 41) == 60;
    assert blended_score(150, -20) == 50;
}
