"""Independent mixed-state oracle for the m-local context service."""

import from services.models { Restaurant, Location, HasLocation }
import from services.importer { upsert_access_notice }
import from services.context { get_access_context }

with entry {
    restaurant = Restaurant(slug="revdev-mixed", name="Mixed (Demo)", is_demo=True);
    root ++> restaurant;
    restaurant +>:HasLocation():+> Location(address="Fictional address", neighborhood="Demo");
    location = [restaurant ->:HasLocation:->][0];
    current = {
        "source_id": "revdev-contract", "external_id": "current", "location_slug": "revdev-mixed",
        "version": "1", "publisher": "Test publisher", "source_url": "",
        "checked_at": 100.0, "valid_from": 100.0, "valid_until": 200.0,
        "summary": "Current notice", "is_demo": True,
        "entrance_instruction": "Current instruction"
    };
    stale = current.copy();
    stale["external_id"] = "stale";
    stale["checked_at"] = 150.0 - 86401.0;
    stale["summary"] = "Stale notice";
    upsert_access_notice(current);
    upsert_access_notice(stale);
    context = get_access_context(jid(location), 150.0);
    assert len(context.notices) == 2;
    assert len([v for v in context.notices if v.state == "current"]) == 1;
    assert len([v for v in context.notices if v.state == "needs_recheck"]) == 1;
    assert len([v for v in context.notices if v.state == "needs_recheck" and v.entrance_instruction == ""]) == 1;
    print(context.state);
}
