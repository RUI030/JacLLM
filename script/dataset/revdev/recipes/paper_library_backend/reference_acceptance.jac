import from datetime { datetime }
import from main { save_paper, list_papers, search_papers_by_tag, get_paper_details }
import from model { Paper }


# ---- Scenario 1: Save a paper successfully ----

test "saves a paper and reports its fields back" {
    w = root spawn save_paper(
        title="DRL for Recommendation",
        author="Priya Nair",
        summary="Offline DRL scales to large recommender systems.",
        tags=["drl", "recsys", "scalability"],
        source_url="https://arxiv.org/example/1",
    );

    assert len(w.reports) == 1;
    envelope = w.reports[0];

    assert envelope["title"] == "DRL for Recommendation";
    assert envelope["author"] == "Priya Nair";
    assert envelope["summary"] == "Offline DRL scales to large recommender systems.";
    assert envelope["tags"] == ["drl", "recsys", "scalability"];
    assert envelope["source_url"] == "https://arxiv.org/example/1";

    # save_paper stamps the timestamp; it must be set (not None).
    assert envelope["created_at"] is not None;

    # The saved node is reachable on root as a Paper.
    papers = [root -->][?:Paper];
    assert any(p.title == "DRL for Recommendation" for p in papers);
}


# ---- Scenario 2: List all papers ----

test "lists every paper currently on root" {
    seed_paper("Graph Neural Networks", "A. Rao", ["gcn"]);
    seed_paper("Transformer Survey", "B. Chen", ["attention", "survey"]);

    w = root spawn list_papers();

    # list_papers reports one Paper per node it gathered. root persists across
    # runs, so we lower-bound the count and check our own seeded titles.
    assert len(w.reports) >= 2;

    titles = [p.title for p in w.reports];
    assert "Graph Neural Networks" in titles;
    assert "Transformer Survey" in titles;
}


# ---- Scenario 3: Search papers by tag ----

test "searches papers by tag and filters correctly" {
    # Use a unique tag so a prior persisted run can't leak extra matches.
    seed_paper("Tagged A", "C. Lee", ["revdev-jpf-search-only"]);
    seed_paper("Tagged B", "D. Kim", ["survey"]);

    w = root spawn search_papers_by_tag(tag="revdev-jpf-search-only");

    assert len(w.reports) == 1;
    envelope = w.reports[0];
    papers = envelope["papers"];

    # Only the paper carrying the tag survives the filter; the non-matching
    # paper is excluded.
    assert len(papers) == 1;
    assert papers[0].title == "Tagged A";
}


# ---- get_paper_details: function endpoint ----

test "retrieves a paper by its generated id" {
    w = root spawn save_paper(
        title="Looked Up Later",
        author="E. Patel",
        summary="Saved then fetched by id.",
        tags=["lookup"],
        source_url="https://arxiv.org/example/6",
    );
    id = w.reports[0]["jid"];
    paper = get_paper_details(id);

    assert paper is not None;
    assert isinstance(paper, Paper);
    assert paper.title == "Looked Up Later";
    assert paper.tags == ["lookup"];
}


test "returns None for an unknown id" {
    # A well-formed UUID-shaped id that isn't stored on root.
    assert get_paper_details("00000000-0000-0000-0000-000000000000") is None;
}


# Seed two papers on root (shared graph state persists between tests).
def seed_paper(title: str, author: str, tags: list[str]) {
    root ++> Paper(title=title, author=author, summary="seed summary", source_url="https://arxiv.org/seed", tags=tags, created_at=datetime.now(),);
}
