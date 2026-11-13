import from server.models { Employee, BusyBlock, Employment, Shift, employee_of, held_shifts }
import from server.rules { Held, Verdict, Ledger, CONFLICT, HOUR_LIMIT }


# Create an employee on root and return its generated id.
def make_employee(name: str, kind: str, status: str, weekly_limit: int) -> str {
    e = Employee(name=name, kind=kind, status=status, weekly_limit=weekly_limit);
    root ++> e;
    return jid(e);
}

# Give the employee an active job (weekly allotment, positions) with employer id did.
def hire(sid: str, did: str, hours: int, positions: list[str]) {
    employee_of(sid) ++> Employment(
        student=sid, employer=did, hours=hours, state="active", positions=positions
    );
}

# Attach a published shift held by sid for the given week.
def give_shift(sid: str, did: str, week: str, day: int, start: int, end: int) {
    employee_of(sid) ++> Shift(
        employer=did, week=week, day=day, start=start, end=end, student=sid, status="published"
    );
}


test "employee caps, daily max and lookup by id" {
    sid = make_employee("Ana Ruiz Cap", "student", "international", 25);
    st = employee_of(sid);
    assert st is not None;
    assert st.first_name() == "Ana";
    assert st.is_international();
    assert st.cap() == 20;
    assert st.daily_max() == 8;
    wid = make_employee("Wes Worker Cap", "worker", "international", 40);
    w = employee_of(wid);
    assert not w.is_international();
    assert w.cap() == 40;
    assert w.daily_max() == 12;
    assert employee_of("") is None;
}


test "ledger reports not_on_team and not_qualified before timing rules" {
    sid = make_employee("Ben Team", "student", "domestic", 20);
    led = Ledger(week="2031-01-06");
    v = led.check(sid, "dept-team-a", 0, 600, 720);
    assert not v.ok;
    assert v.code == "not_on_team";
    assert v.public_reason() == "not_on_team";
    hire(sid, "dept-team-b", 10, ["pos-cashier"]);
    led2 = Ledger(week="2031-01-06");
    assert led2.allotment(sid, "dept-team-b") == 10;
    assert led2.roles(sid, "dept-team-b") == ["pos-cashier"];
    q = led2.check(sid, "dept-team-b", 0, 600, 720, None, "pos-cook");
    assert q.code == "not_qualified";
    ok = led2.check(sid, "dept-team-b", 0, 600, 720, None, "pos-cashier");
    assert ok.ok;
    assert ok.hours_left == 10.0;
}


test "busy blocks and held shifts produce schedule_conflict" {
    sid = make_employee("Cara Busy", "student", "domestic", 20);
    hire(sid, "dept-busy", 15, []);
    employee_of(sid) ++> BusyBlock(day=1, start=540, end=660, title="Lecture", week="");
    give_shift(sid, "dept-other", "2031-02-03", 2, 600, 780);
    led = Ledger(week="2031-02-03");
    v = led.check(sid, "dept-busy", 1, 600, 720);
    assert not v.ok;
    assert v.code == "overlap";
    assert v.is_timing();
    assert v.public_reason() == CONFLICT;
    assert v.hours_left == 15.0;
    x = led.check(sid, "dept-busy", 2, 720, 840);
    assert x.code == "overlap";
    assert x.cross_department;
    free = led.check(sid, "dept-busy", 3, 600, 720);
    assert free.ok;
    assert len(held_shifts(employee_of(sid), "2031-02-03")) == 1;
}


test "compliance enforces weekly cap, rest gap and daily max" {
    sid = make_employee("Dev Intl", "student", "international", 30);
    hire(sid, "dept-cap", 30, []);
    wk = "2031-03-03";
    give_shift(sid, "dept-cap", wk, 0, 480, 960);
    give_shift(sid, "dept-cap", wk, 1, 480, 960);
    led = Ledger(week=wk);
    assert led.total_hours(sid) == 16.0;
    assert led.cap_left(sid) == 4.0;
    v = led.check(sid, "dept-cap", 2, 480, 780);
    assert v.code == "weekly_cap";
    assert v.is_hours();
    assert v.public_reason() == HOUR_LIMIT;
    assert v.hours_left == 4.0;
    r = led.check(sid, "dept-cap", 0, 975, 1035);
    assert r.code == "daily_max";
    led.remove(sid, led.held(sid)[0].shift_id);
    assert led.total_hours(sid) == 8.0;
    rest = led.check(sid, "dept-cap", 1, 975, 1035);
    assert rest.code == "daily_max";
    led.remove(sid, led.held(sid)[0].shift_id);
    gap = led.check(sid, "dept-cap", 4, 480, 600);
    assert gap.ok;
    led.add(sid, Held(shift_id="tmp-1", department_id="dept-cap", day=4, start=480, end=600));
    short = led.check(sid, "dept-cap", 4, 615, 700);
    assert short.code == "rest";
    assert short.public_reason() == CONFLICT;
}


test "clone isolates held shifts and violations lists every broken rule" {
    sid = make_employee("Eli Clone", "student", "domestic", 20);
    hire(sid, "dept-clone", 6, []);
    led = Ledger(week="2031-04-07");
    led.add(sid, Held(shift_id="c1", department_id="dept-clone", day=0, start=480, end=720));
    other = led.clone();
    other.add(sid, Held(shift_id="c2", department_id="dept-clone", day=0, start=700, end=900));
    assert led.total_hours(sid) == 4.0;
    assert len(other.held(sid)) == 2;
    assert led.violations(sid) == [];
    assert other.violations(sid) == ["overlap", "dept_hours"];
    other.remove(sid, "c2");
    other.add(sid, Held(shift_id="c3", department_id="dept-x", day=0, start=730, end=780));
    assert other.violations(sid) == ["rest", "dept_hours"];
}
