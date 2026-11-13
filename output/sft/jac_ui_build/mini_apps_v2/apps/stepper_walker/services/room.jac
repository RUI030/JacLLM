"""The room temperature kept under root."""

node RoomDial {
    has degrees: int = 20;
}

walker:pub open_room {
    can start with Root entry {
        if not [-->][?:RoomDial] {
            here ++> RoomDial(degrees=20);
        }
        visit [-->][?:RoomDial];
    }

    can collect with RoomDial entry {
        report here;
    }
}

walker:pub warm_up {
    can start with Root entry {
        if not [-->][?:RoomDial] {
            here ++> RoomDial(degrees=20);
        }
        visit [-->][?:RoomDial];
    }

    can raise_it with RoomDial entry {
        here.degrees = here.degrees + 1;
        report here;
    }
}

walker:pub cool_down {
    can start with Root entry {
        if not [-->][?:RoomDial] {
            here ++> RoomDial(degrees=20);
        }
        visit [-->][?:RoomDial];
    }

    can lower_it with RoomDial entry {
        here.degrees = here.degrees - 1;
        report here;
    }
}

walker:pub reset_room {
    can start with Root entry {
        if not [-->][?:RoomDial] {
            here ++> RoomDial(degrees=20);
        }
        visit [-->][?:RoomDial];
    }

    can restore with RoomDial entry {
        here.degrees = 20;
        report here;
    }
}
