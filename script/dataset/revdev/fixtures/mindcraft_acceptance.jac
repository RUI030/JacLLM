"""Independent acceptance checks for the scoped Mindcraft pilot."""
import from services.island {
    get_world, manifest_emotion, place_entity, apply_interaction,
    commit_value_action, get_act_path, reset_demo
}

test "check-in placement interaction intention and reset" {
    root spawn reset_demo();
    world = (root spawn get_world()).reports[0];
    assert len(world["entities"]) == 0;
    assert "breathe" in world["interactions"];
    created = (root spawn manifest_emotion(text="I feel worried about tomorrow")).reports[0];
    assert not created["crisis"];
    assert len(created["entities"]) > 0;
    item = created["entities"][0];
    entity_id = item["id"];
    assert not item["placed"];
    placed = (root spawn place_entity(entity_id=entity_id, x=30, y=60)).reports[0];
    assert placed["entity"]["placed"];
    assert placed["entity"]["x"] == 30;
    action = (root spawn apply_interaction(entity_id=entity_id, kind="breathe")).reports[0];
    assert action["event"]["kind"] == "breathe";
    root spawn commit_value_action(entity_id=entity_id, value="connection", action="Call a friend");
    path = (root spawn get_act_path(entity_id=entity_id)).reports[0];
    assert len(path["events"]) == 1;
    assert path["actions"][0]["action"] == "Call a friend";
    assert len((root spawn get_world()).reports[0]["entities"]) > 0;
    root spawn reset_demo();
    assert len((root spawn get_world()).reports[0]["entities"]) == 0;
}

test "crisis input produces guidance and no graph entity" {
    root spawn reset_demo();
    response = (root spawn manifest_emotion(text="I want to kill myself")).reports[0];
    assert response["crisis"];
    assert len(response["message"]) > 20;
    assert len(response["entities"]) == 0;
    assert len((root spawn get_world()).reports[0]["entities"]) == 0;
}

test "blank input and invalid entity do not create state" {
    root spawn reset_demo();
    response = (root spawn manifest_emotion(text="   ")).reports[0];
    assert "error" in response;
    invalid = (root spawn place_entity(entity_id="does-not-exist", x=20, y=20)).reports[0];
    assert "error" in invalid;
    assert len((root spawn get_world()).reports[0]["entities"]) == 0;
}
