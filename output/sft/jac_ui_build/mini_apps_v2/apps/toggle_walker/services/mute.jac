"""The do-not-disturb flag kept under root."""

node MuteFlag {
    has muted: bool = False;
}

walker:pub read_mute {
    can start with Root entry {
        if not [-->][?:MuteFlag] {
            here ++> MuteFlag(muted=False);
        }
        visit [-->][?:MuteFlag];
    }

    can collect with MuteFlag entry {
        report here;
    }
}

walker:pub flip_mute {
    can start with Root entry {
        if not [-->][?:MuteFlag] {
            here ++> MuteFlag(muted=False);
        }
        visit [-->][?:MuteFlag];
    }

    can flip with MuteFlag entry {
        here.muted = not here.muted;
        report here;
    }
}
