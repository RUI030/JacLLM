import from services.nourish_model {
    HubNode, BusinessNode, ShelterNode, DonationNode, VolunteerNode, Offers
}
import from services.supply_agent { supply_manager }


def make_business(name: str) -> BusinessNode {
    biz = BusinessNode(
        name=name,
        location="1 Test St",
        business_type="supermarket",
        contact=name + "@example.com"
    );
    root ++> biz;
    return biz;
}


test "valid upload creates a pending donation and reports it" {
    biz = make_business("Revdev Nourish Mart A");
    w = biz spawn supply_manager(
        food_type="revdev-carrots", quantity=42, expiry_time="2099-12-31T18:00:00"
    );

    assert len(w.reports) == 1;
    r = w.reports[0];
    assert r == {
        "status": "created",
        "business": "Revdev Nourish Mart A",
        "food_type": "revdev-carrots",
        "quantity": 42,
        "expiry_time": "2099-12-31T18:00:00"
    };

    assert w.error_message == "";
    d = w.created_donation;
    assert d is not None;
    assert isinstance(d, DonationNode);
    assert d.food_type == "revdev-carrots";
    assert d.quantity == 42;
    assert d.expiry_time == "2099-12-31T18:00:00";
    assert d.status == "pending";
    assert d.dispatched == False;
}


test "created donation is linked by an Offers edge and anchored to root" {
    biz = make_business("Revdev Nourish Bistro B");
    w = biz spawn supply_manager(
        food_type="revdev-bread", quantity=7, expiry_time="2098-01-01T00:00:00"
    );

    offered = [biz ->:Offers:->][?:DonationNode];
    assert len(offered) == 1;
    assert offered[0].food_type == "revdev-bread";

    on_root = [root -->][?:DonationNode];
    assert any(x.food_type == "revdev-bread" and x.quantity == 7 for x in on_root);
}


test "expired upload is rejected with an error report and no donation" {
    biz = make_business("Revdev Nourish Mart C");
    w = biz spawn supply_manager(
        food_type="revdev-old-salad", quantity=5, expiry_time="2000-01-01T00:00:00"
    );

    expected = "REJECTED: Food 'revdev-old-salad' from 'Revdev Nourish Mart C' is already expired (expiry=2000-01-01T00:00:00).";
    assert len(w.reports) == 1;
    assert w.reports[0] == {"status": "error", "message": expected};
    assert w.error_message == expected;
    assert w.created_donation is None;

    assert len([biz ->:Offers:->][?:DonationNode]) == 0;
    on_root = [root -->][?:DonationNode];
    assert not any(x.food_type == "revdev-old-salad" for x in on_root);
}


test "each upload on the same business adds another offered donation" {
    biz = make_business("Revdev Nourish Mart D");
    biz spawn supply_manager(food_type="revdev-rice", quantity=10, expiry_time="2099-06-01T12:00:00");
    biz spawn supply_manager(food_type="revdev-beans", quantity=3, expiry_time="2099-06-02T12:00:00");
    biz spawn supply_manager(food_type="revdev-stale", quantity=1, expiry_time="1999-12-31T23:59:59");

    offered = [biz ->:Offers:->][?:DonationNode];
    kinds = sorted([x.food_type for x in offered]);
    assert kinds == ["revdev-beans", "revdev-rice"];
}


test "model nodes expose their declared defaults" {
    hub = HubNode();
    assert hub.name == "Nourish Hub";

    d = DonationNode(food_type="revdev-milk", quantity=2, expiry_time="2099-01-01T00:00:00");
    assert d.status == "pending";
    assert d.dispatched == False;

    v = VolunteerNode(name="Revdev Driver", vehicle_type="van", location="X", contact="+1-555");
    assert v.is_available == True;

    s = ShelterNode(name="Revdev Shelter", location="Y", current_capacity=1, max_capacity=5, needed_items=["bread"]);
    assert s.needed_items == ["bread"];
}
