test "new session retires previous active session" {
    first = start_pomodoro("first-event");
    second = start_pomodoro("second-event");
    assert first.phase == "done" and not first.running;
    assert second.phase == "work" and second.running;
    assert second.event_id == "second-event";
}

test "two work cycles alternate breaks then finish" {
    ev = create_event(2026, 11, 1, 10, 0, "Write report", "", 25, 5, 2);
    session = start_pomodoro(jid(ev));
    advance_phase(jid(session));
    assert session.phase == "break" and session.cycle_ix == 0;
    advance_phase(jid(session));
    assert session.phase == "work" and session.cycle_ix == 1;
    advance_phase(jid(session));
    assert session.phase == "done" and not session.running;
}

test "settings persist idle text in one singleton" {
    first = get_settings();
    changed = set_idle_text("Ready");
    assert jid(first) == jid(changed);
    assert get_settings().idle_text == "Ready";
}
