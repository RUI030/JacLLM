import from jaclang.byllm.lib { MockLLM }
import abilities.llm_abilities as abilities;
import from graph.nodes.patient { Patient }
import from graph.nodes.document { Document }
import from graph.walkers.intake.document_classify { DocumentClassify }
import from graph.walkers.intake.plain_english_translator { PlainEnglishTranslator }


test "classifies an unknown document with the model's category" {
    abilities.llm = MockLLM(model_name="mockllm", config={"outputs": ["EOB"]});
    p = Patient(name="Ada Classify");
    doc = Document(
        doc_id="aw-cls-1",
        raw_content="Medicare Summary Notice ... Explanation of Benefits",
        source="upload",
        original_filename="msn.pdf",
        mime_type="application/pdf"
    );
    p ++> doc;
    p spawn DocumentClassify();
    assert doc.classification == "EOB";
    assert doc.plain_english_summary == "";
}


test "classifies every unknown document in connection order" {
    abilities.llm = MockLLM(
        model_name="mockllm",
        config={"outputs": ["MEDICAL_BILL", "POWER_OF_ATTORNEY"]}
    );
    p = Patient(name="Ben Twodocs");
    first = Document(doc_id="aw-cls-2a", raw_content="Statement of charges");
    second = Document(doc_id="aw-cls-2b", raw_content="Durable power of attorney");
    p ++> first;
    p ++> second;
    p spawn DocumentClassify();
    assert first.classification == "MEDICAL_BILL";
    assert second.classification == "POWER_OF_ATTORNEY";
}


test "an already classified document halts classification" {
    abilities.llm = MockLLM(model_name="mockllm", config={"outputs": ["SCAM_COMMUNICATION"]});
    p = Patient(name="Cy Halted");
    done = Document(doc_id="aw-cls-3a", raw_content="Last will", classification="WILL");
    pending = Document(doc_id="aw-cls-3b", raw_content="You won a prize");
    p ++> done;
    p ++> pending;
    p spawn DocumentClassify();
    assert done.classification == "WILL";
    assert pending.classification == "UNKNOWN";
}


test "translates a classified document into a plain-English summary" {
    abilities.llm = MockLLM(
        model_name="mockllm",
        config={"outputs": ["Your doctor visit cost $120. Bottom line: you owe $20."]}
    );
    p = Patient(name="Dee Translate");
    doc = Document(doc_id="aw-tr-1", raw_content="CPT 99213 billed 120.00 allowed 100.00", classification="EOB");
    p ++> doc;
    p spawn PlainEnglishTranslator();
    assert doc.plain_english_summary == "Your doctor visit cost $120. Bottom line: you owe $20.";
    assert doc.classification == "EOB";
}


test "translation skips documents without content and stops there" {
    abilities.llm = MockLLM(model_name="mockllm", config={"outputs": ["should not be used"]});
    p = Patient(name="Eve Empty");
    empty = Document(doc_id="aw-tr-2a", raw_content="", classification="UNKNOWN");
    later = Document(doc_id="aw-tr-2b", raw_content="Notice of policy change", classification="POLICY_CHANGE");
    p ++> empty;
    p ++> later;
    p spawn PlainEnglishTranslator();
    assert empty.plain_english_summary == "";
    assert later.plain_english_summary == "";
}


test "classification then translation fills both fields" {
    abilities.llm = MockLLM(model_name="mockllm", config={"outputs": ["MSN_PART_B", "Medicare paid most of it. Bottom line: you owe nothing."]});
    p = Patient(name="Fay Pipeline");
    doc = Document(doc_id="aw-pipe-1", raw_content="Medicare Summary Notice Part B");
    p ++> doc;
    p spawn DocumentClassify();
    p spawn PlainEnglishTranslator();
    assert doc.classification == "MSN_PART_B";
    assert doc.plain_english_summary == "Medicare paid most of it. Bottom line: you owe nothing.";
}
