# Record

```json
{
  "source": "code",
  "format": "repo",
  "class": "function",
  "task_type": "scaffold2impl",
  "fp": "JacHackA2Tech/Sahil0445__campussync::tests/ai_check.jac"
}
```

## SYSTEM

```
You are a helpful assistant.
```

## USER

The Jac file below has its function, ability, and entry-block bodies stripped to `{ ... }`. Complete each body so the file is fully implemented. Reply with the code only.

```jac
"""AI path check with byLLM's MockLLM: typed answers flow through every agent, failures fall back."""

import from jaclang.byllm.lib { MockLLM }
import server.ai as ai;
import server.availability as availability;
import server.needs as needs;
import server.copilot as copilot;

with entry:__main__ { ... }
```

## ASSISTANT

"""AI path check with byLLM's MockLLM: typed answers flow through every agent, failures fall back."""

import from jaclang.byllm.lib { MockLLM }
import server.ai as ai;
import server.availability as availability;
import server.needs as needs;
import server.copilot as copilot;

with entry:__main__ {
    setattr(ai, "GEMINI_API_KEY", "test");
    import server.config as config;
    setattr(config, "GEMINI_API_KEY", "test");
    mock = MockLLM(outputs=[
        ai.NoteRules(rules=[ai.NoteRule(days=[4], start="00:00", end="10:00")]),
        ai.NeedsPlan(needs=[ai.NeedBlock(days=[0, 1, 2, 3, 4, 5, 6], start="07:00", end="19:00", headcount=1, role="Site guard")], summary="One guard all day."),
        ai.DeptIntent(intent="check", student="Priya", day=2, start="12:00", end="15:00"),
        ai.StudentIntent(intent="unavailable", unavailable=[ai.Unavail(day=5, recurring=False, label="Family visit")], want_days=[2])
    ]);
    setattr(ai, "gemini", mock);
    ai._cooldown_until = 0.0;
    print("enabled:", ai.enabled(), "ready:", ai.ready());
    (rules, used) = availability.parse_note("No Fridays before 10");
    print("note:", used, rules);
    (rows, summary, used2) = needs.generate("guards", [{"id": "p1", "name": "Site guard"}], "business");
    print("needs:", used2, len(rows), rows[0], summary);
    (intent, used3) = copilot.parse_dept("Can Priya work Wed 12 to 3?", [("s1", "Priya Nair"), ("s2", "Sam Ortiz")]);
    print("dept:", used3, intent);
    (sint, used4) = copilot.parse_student("I can't do Saturday, Wednesday works");
    print("student:", used4, sint);
}
