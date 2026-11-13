"""Cat and dog votes, kept on a single Ballot node under root."""

node Ballot {
    has cats: int = 0;
    has dogs: int = 0;
}

def _ballot() -> Ballot {
    found = [root-->][?:Ballot];
    if found {
        return found[0];
    }
    ballot = Ballot();
    root ++> ballot;
    return ballot;
}

def:pub read_votes() -> Ballot {
    return _ballot();
}

def:pub vote(side: str) -> Ballot {
    ballot = _ballot();
    if side == "cats" {
        ballot.cats = ballot.cats + 1;
    } elif side == "dogs" {
        ballot.dogs = ballot.dogs + 1;
    }
    return ballot;
}
