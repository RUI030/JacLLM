import os;
import from jaclang.byllm.lib { Model, MockLLM }
import from ai.models { ai_switched_off, model_ready }
import from ai.guide { guide_ready, answer_task_question, GuideAnswer }
import from ai.translate {
    translator_ready,
    translate,
    translate_post,
    translate_batch,
    Translation,
    PostText,
    PostTranslations,
    TextList
}
import ai.guide as g;
import ai.translate as t;


def mock(outputs: list) -> MockLLM {
    return MockLLM(model_name="mockllm", config={"outputs": outputs});
}


test "model_ready rejects None and always accepts a test double" {
    assert model_ready(None) == False;
    assert model_ready(mock([])) == True;
}


test "a real model is not ready when AI is switched off or no API key is set" {
    old_off = os.environ.get("UARRIVED_AI_OFF");
    old_key = os.environ.get("ANTHROPIC_API_KEY");
    real = Model(model_name="claude-haiku-4-5-20251001");
    try {
        os.environ["UARRIVED_AI_OFF"] = "1";
        os.environ["ANTHROPIC_API_KEY"] = "revdev-placeholder";
        assert ai_switched_off() == True;
        assert model_ready(real) == False;
        t.translator = real;
        assert translator_ready() == False;

        os.environ["UARRIVED_AI_OFF"] = "0";
        assert ai_switched_off() == False;
        os.environ["ANTHROPIC_API_KEY"] = "   ";
        assert translator_ready() == False;
        os.environ["ANTHROPIC_API_KEY"] = "revdev-placeholder";
        assert translator_ready() == True;
    } finally {
        if old_off is None {
            os.environ.pop("UARRIVED_AI_OFF", None);
        } else {
            os.environ["UARRIVED_AI_OFF"] = old_off;
        }
        if old_key is None {
            os.environ.pop("ANTHROPIC_API_KEY", None);
        } else {
            os.environ["ANTHROPIC_API_KEY"] = old_key;
        }
    }
}


test "guide readiness follows the guide glob through model_ready" {
    g.guide = mock([GuideAnswer(text="Bring your passport and I-20.")]);
    assert guide_ready() == True;
    answer = answer_task_question(
        "Check in at the International Center.", "", "What do I bring?", "en"
    );
    assert isinstance(answer, GuideAnswer);
    assert answer.text == "Bring your passport and I-20.";
    g.guide = None;
    assert guide_ready() == False;
}


test "translation functions return the typed objects from the translator glob" {
    t.translator = mock(
        [
            Translation(text="Desk for 20 dollars"),
            PostTranslations(
                items=[
                    PostText(language="ko", title="책상", description="20달러 책상"),
                    PostText(language="zh", title="书桌", description="20美元的书桌")
                ]
            ),
            TextList(texts=["hello", "pickup at 5"])
        ]
    );
    assert translator_ready() == True;
    one = translate("책상 20달러", "ko", "en");
    assert isinstance(one, Translation);
    assert one.text == "Desk for 20 dollars";
    post = translate_post("Desk", "Desk for $20", "en", ["ko", "zh"]);
    assert isinstance(post, PostTranslations);
    assert [p.language for p in post.items] == ["ko", "zh"];
    assert post.items[1].title == "书桌";
    batch = translate_batch(["안녕", "5시 픽업"], "ko", "en");
    assert isinstance(batch, TextList);
    assert batch.texts == ["hello", "pickup at 5"];
    t.translator = None;
    assert translator_ready() == False;
}
