"""Two teams kept under root, each with a name and a score."""

node Team {
    has name: str;
    has score: int = 0;
}

walker:pub open_scoreboard {
    can start with Root entry {
        if not [-->][?:Team] {
            here ++> Team(name="Home", score=0);
            here ++> Team(name="Away", score=0);
        }
        visit [-->][?:Team];
    }

    can collect with Team entry {
        report here;
    }
}

walker:pub add_point {
    has team: str;

    can start with Root entry {
        visit [-->][?:Team][?name == self.team];
    }

    can bump with Team entry {
        here.score = here.score + 1;
        report here;
    }
}

walker:pub reset_scores {
    can start with Root entry {
        visit [-->][?:Team];
    }

    can clear with Team entry {
        here.score = 0;
        report here;
    }
}
