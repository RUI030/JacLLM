"""One saved badge colour kept under root."""

node BadgeColour {
    has shade: str = "";
}

walker:pub open_colour {
    can start with Root entry {
        if not [-->][?:BadgeColour] {
            here ++> BadgeColour(shade="");
        }
        visit [-->][?:BadgeColour];
    }

    can collect with BadgeColour entry {
        report here;
    }
}

walker:pub save_colour {
    has colour: str;

    can start with Root entry {
        if not [-->][?:BadgeColour] {
            here ++> BadgeColour(shade="");
        }
        visit [-->][?:BadgeColour];
    }

    can store with BadgeColour entry {
        here.shade = self.colour;
        report here;
    }
}
