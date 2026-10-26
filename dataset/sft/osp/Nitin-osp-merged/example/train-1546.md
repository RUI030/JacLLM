# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "osp",
  "fp": "osp_A_11__composer_v28",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp_A_11__composer_v28",
  "tier": "legacy_test_verified",
  "verification": "check+tests",
  "n_tokens": 418,
  "n_answer_tokens": 330
}
```

## USER

In my restaurant recommender, restaurants are nodes with a name, cuisine, and rating. I want one finder walker that takes a minimum rating as a spawn parameter rather than hardcoding it. Spawn it twice from root — once at 4.5+ for date night, once at 3.5+ for casual lunch — and print the matches from each pass.

## ASSISTANT

"""Restaurant recommender: walk the dining graph and match spots by minimum rating."""

node Restaurant {
    has name: str = "";
    has cuisine: str = "";
    has rating: float = 0.0;
}

walker Finder {
    has min_rating: float = 0.0;
    has pass_label: str = "";

    can start with Root entry {
        hdr = self.pass_label + " (min rating " + str(self.min_rating) + "+):";
        print(hdr);
        visit [-->];
    }

    can inspect with Restaurant entry {
        if here.rating >= self.min_rating {
            print(f"  * {here.name} — {here.cuisine} ({here.rating})");
        }
        visit [-->];
    }
}

with entry {
    root ++> Restaurant(name="Le Petit Chef", cuisine="French", rating=4.8)
        ++> Restaurant(name="Marina Grill", cuisine="Seafood", rating=4.2)
        ++> Restaurant(name="Noodle House", cuisine="Asian", rating=3.6)
        ++> Restaurant(name="Quick Bites", cuisine="American", rating=3.4)
        ++> Restaurant(name="Corner Cafe", cuisine="Cafe", rating=3.5);

    root spawn Finder(min_rating=4.5, pass_label="Date night");
    root spawn Finder(min_rating=3.5, pass_label="Casual lunch");
}
