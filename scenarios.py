"""
The runs your test needs. ← UNIT 4, MILESTONE 3

Each of your five criteria needs something run against it. A criterion about
the empty-search branch needs an impossible query. One about the fit card needs
the same item run more than once. Working that out is Milestone 3's first step,
and this file is where you write it down.

`run_eval.py` runs everything here five times and writes the run log — five
because your criteria are written out of five.

Three scenarios are filled in to show the shape. Add or change whatever your
own criteria need — these are a starting point, not a fixed set.
"""

SCENARIOS = [
    {
        # A query the data can match. Criterion 1.
        "name": "matching query completes",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 1,
    },
    {
        # A query nothing can match. Criterion 2 — the branch.
        "name": "impossible query stops early",
        "query": "designer ballgown size XXS under $5",
        "wardrobe": "example",
        "criterion": 2,
    },
    {
        "name": "selected item reaches outfit tool unchanged",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        # Repeating this scenario five times keeps the selected listing fixed.
        "name": "fit card includes full title, price, and platform once",
        "query": "graphic tee under $30, size M",
        "wardrobe": "example",
        "criterion": 4,
    },
    {
        # Each try runs all five searches from criterion 5, without model calls.
        "name": "five known-match searches respect the price ceiling",
        "kind": "search_batch",
        "descriptions": ["graphic tee", "flannel", "tank", "belt", "vintage"],
        "size": None,
        "max_price": 30.0,
        "criterion": 5,
    },
    {
        # A user with nothing saved. One of unit 4's three failure modes.
        "name": "empty wardrobe",
        "query": "denim jacket under $50",
        "wardrobe": "empty",
        "criterion": None,
    },
]

WARDROBES = ("example", "empty")


def validate() -> list[str]:
    """Complain about anything malformed, before a long run rather than during."""
    problems = []
    for i, scenario in enumerate(SCENARIOS, 1):
        kind = scenario.get("kind", "agent")
        if kind == "search_batch":
            descriptions = scenario.get("descriptions")
            if not isinstance(descriptions, list) or not descriptions or any(
                not isinstance(description, str) or not description.strip()
                for description in descriptions
            ):
                problems.append(f"scenario {i} needs nonempty search descriptions")
            if not isinstance(scenario.get("max_price"), (int, float)):
                problems.append(f"scenario {i} needs a numeric max_price")
            continue
        if kind != "agent":
            problems.append(f"scenario {i} has unknown kind {kind!r}")
        if not scenario.get("query", "").strip():
            problems.append(f"scenario {i} has no query")
        if scenario.get("wardrobe") not in WARDROBES:
            problems.append(
                f"scenario {i} has wardrobe {scenario.get('wardrobe')!r} — "
                f"it should be one of {WARDROBES}"
            )
    return problems
