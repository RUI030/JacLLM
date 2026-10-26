# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "osp",
  "task_type": "osp",
  "fp": "osp_C_42__mm3_v63",
  "origin_file": "osp_merged_corpus.jsonl",
  "origin_id": "osp_C_42__mm3_v63",
  "tier": "legacy_test_verified",
  "verification": "check+tests",
  "n_tokens": 562,
  "n_answer_tokens": 500
}
```

## USER

Model a city as stations connected to hotels and attractions, each attraction carrying a star rating. From every station, shortlist only the attractions (ignore hotels) and then only those rated 4 stars or higher, and print the final itinerary.

## ASSISTANT

"""City guide: stations connect to hotels and attractions; a walker from each station
shortlists only attractions rated 4 stars or higher and prints the itinerary."""

node Station {
    has name: str = "";
}

node Hotel {
    has name: str = "";
    has nightly_rate: float = 0.0;
}

node Attraction {
    has name: str = "";
    has stars: int = 0;
}

edge ConnectsTo {}

walker Tourist {
    can start with Root entry {
        visit [-->];
    }

    can arrive with Station entry {
        print(f"Arrived at station: {here.name}");
        visit [-->];
    }

    # Only attractions are reviewed; hotels are skipped via a separate ability.
    can skip_hotel with Hotel entry {
        print(f"  (skipping hotel: {here.name})");
        visit [-->];
    }

    can review with Attraction entry {
        status = "SHORTLIST" if here.stars >= 4 else "PASS";
        print(f"  [{status}] {here.name} ({here.stars}★)");
        visit [-->];
    }
}

with entry {
    central = Station(name="Central Station");
    riverside = Station(name="Riverside Station");

    # Stations connect to hotels and attractions via ConnectsTo edges.
    central +>:ConnectsTo:+> Hotel(name="Grand Plaza", nightly_rate=220.0);
    central +>:ConnectsTo:+> Attraction(name="City Museum", stars=5);
    central +>:ConnectsTo:+> Attraction(name="Old Bridge", stars=3);

    riverside +>:ConnectsTo:+> Hotel(name="Riverside Inn", nightly_rate=95.0);
    riverside +>:ConnectsTo:+> Attraction(name="Harbor Cruise", stars=4);
    riverside +>:ConnectsTo:+> Attraction(name="Lighthouse Walk", stars=4);
    riverside +>:ConnectsTo:+> Attraction(name="Dockside Cafe", stars=2);

    root spawn Tourist();
    print("---");
    root spawn Tourist();
}
