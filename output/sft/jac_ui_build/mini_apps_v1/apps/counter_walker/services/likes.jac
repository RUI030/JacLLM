"""One like counter kept under root."""

node LikeCount {
    has total: int = 0;
}

walker:pub open_likes {
    can start with Root entry {
        if not [-->][?:LikeCount] {
            here ++> LikeCount(total=0);
        }
        visit [-->][?:LikeCount];
    }

    can collect with LikeCount entry {
        report here;
    }
}

walker:pub add_like {
    can start with Root entry {
        if not [-->][?:LikeCount] {
            here ++> LikeCount(total=0);
        }
        visit [-->][?:LikeCount];
    }

    can bump with LikeCount entry {
        here.total = here.total + 1;
        report here;
    }
}
