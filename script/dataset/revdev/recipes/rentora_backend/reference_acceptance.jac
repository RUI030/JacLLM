import from main {
    add_property_node,
    list_properties,
    list_units,
    register_tenant,
    list_tenants,
    match_tenant,
    list_tickets,
    approve_dispatch,
    resolve_ticket,
    delete_property_node
}
import from services.graph.models { Property, Unit, Ticket, HasUnit, HasTicket }


test "adding a property with units shows up in the property listing" {
    w = root spawn add_property_node(
        name="RevDev Maple Court", address="1 Maple St", unit_numbers=["101", "102", "103"]
    );
    assert len(w.reports) == 1;
    created = w.reports[0];
    assert created["status"] == "created";
    assert created["property"] == "RevDev Maple Court";
    assert created["units"] == 3;

    listing = root spawn list_properties();
    rows = listing.reports[0];
    mine = [r for r in rows if r["id"] == created["id"]];
    assert len(mine) == 1;
    assert mine[0]["name"] == "RevDev Maple Court";
    assert mine[0]["address"] == "1 Maple St";
    assert mine[0]["unit_count"] == 3;

    # The Property node is attached to root and owns its units via HasUnit.
    props = [p for p in [root -->][?:Property] if p.name == "RevDev Maple Court"];
    assert len(props) == 1;
    assert sorted([u.number for u in [props[0] ->: HasUnit :->]]) == ["101", "102", "103"];
}


test "registering a tenant creates a lease and is visible in listings and phone match" {
    root spawn add_property_node(name="RevDev Birch House", address="2 Birch Rd", unit_numbers=["1a"]);
    w = root spawn register_tenant(
        tenant_name="Ada Revdev", tenant_phone="+15550100201", tenant_email="ada@example.com",
        unit_number="1a", rent_amount=1250.0, lease_start="2026-01-01", lease_end="2026-12-31",
        property_name="RevDev Birch House"
    );
    assert len(w.reports) == 1;
    reg = w.reports[0];
    assert reg["status"] == "registered";
    assert reg["unit"] == "1a";
    assert reg["property"] == "RevDev Birch House";
    assert reg["id"] != "";

    again = root spawn register_tenant(
        tenant_name="Ada Revdev", tenant_phone="+15550100201", unit_number="1A",
        rent_amount=1250.0, property_name="RevDev Birch House"
    );
    assert again.reports[0]["status"] == "already_registered";

    tenants = root spawn list_tenants();
    mine = [t for t in tenants.reports[0] if t["phone_number"] == "+15550100201"];
    assert len(mine) == 1;
    assert mine[0]["full_name"] == "Ada Revdev";
    assert mine[0]["unit_number"] == "1a";
    assert mine[0]["property_name"] == "RevDev Birch House";
    assert mine[0]["rent"] == 1250.0;
    assert mine[0]["lease_end"] == "2026-12-31";

    units = root spawn list_units();
    birch = [u for u in units.reports if u["property"] == "RevDev Birch House"];
    assert len(birch) == 1;
    assert birch[0]["tenant"] == "Ada Revdev";
    assert birch[0]["rent"] == 1250.0;

    m = root spawn match_tenant(phone="+15550100201");
    assert m.reports[0]["matched"] == True;
    assert m.reports[0]["tenant_name"] == "Ada Revdev";
    assert m.reports[0]["unit"] == "1a";
}


test "matching an unknown phone reports no match" {
    m = root spawn match_tenant(phone="+15559999999-revdev");
    assert len(m.reports) == 1;
    assert m.reports[0] == {"matched": False};
}


test "dispatching and resolving a ticket updates its status" {
    root spawn add_property_node(name="RevDev Cedar Flats", address="3 Cedar Ln", unit_numbers=["7"]);
    prop = [p for p in [root -->][?:Property] if p.name == "RevDev Cedar Flats"][0];
    unit = [prop ->: HasUnit :->][0];
    unit +>: HasTicket :+> Ticket(
        ticket_id="RD-TKT-0001", category="plumbing", description="Leaky sink",
        urgency="high", vendor_name="Quick Flow Plumbing", estimated_cost=150.0
    );

    listed = root spawn list_tickets();
    mine = [t for t in listed.reports if t["ticket_id"] == "RD-TKT-0001"];
    assert len(mine) == 1;
    assert mine[0]["status"] == "open";
    assert mine[0]["unit"] == "7";

    d = root spawn approve_dispatch(ticket_id="RD-TKT-0001");
    assert len(d.reports) == 1;
    assert d.reports[0]["status"] == "dispatched";
    assert d.reports[0]["vendor_name"] == "Quick Flow Plumbing";
    assert d.reports[0]["unit"] == "7";
    assert d.reports[0]["estimated_cost"] == 150.0;

    r = root spawn resolve_ticket(ticket_id="RD-TKT-0001");
    assert len(r.reports) == 1;
    assert r.reports[0]["status"] == "resolved";
    assert r.reports[0]["resolved_at"] != "";

    after = [t for t in (root spawn list_tickets()).reports if t["ticket_id"] == "RD-TKT-0001"];
    assert after[0]["status"] == "resolved";
}


test "deleting a property removes it and unknown ids report not_found" {
    created = (root spawn add_property_node(name="RevDev Doomed Lofts", address="4 Gone Ave", unit_numbers=[])).reports[0];
    missing = root spawn delete_property_node(property_id="revdev-no-such-id");
    assert missing.reports[-1] == {"status": "not_found"};

    gone = root spawn delete_property_node(property_id=created["id"]);
    assert gone.reports == [{"status": "deleted"}];
    ids = [r["id"] for r in (root spawn list_properties()).reports[0]];
    assert created["id"] not in ids;
}
