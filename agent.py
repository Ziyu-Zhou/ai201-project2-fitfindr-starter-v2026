"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import math
import re

import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable


# Match complete filter values so malformed inputs cannot become partial filters.
_PRICE_FILTER = re.compile(
    r"\bunder\s+\$?\s*(?P<price>[+-]?(?:\d+(?:\.\d+)?|\.\d+))(?!,\d)(?=$|[\s,;])",
    re.IGNORECASE,
)
_CLOTHING_SIZE = r"(?:XXXS|XXS|XS|S|M|L|XL|XXL|XXXL)"
_SIZE_FILTER = re.compile(
    r"\b(?:in\s+)?size\s+(?P<size>"
    r"one\s+size|"
    r"US\s+\d+(?:\.\d+)?|"
    r"W\d+(?:\s+L\d+)?|"
    rf"{_CLOTHING_SIZE}(?:\s*/\s*{_CLOTHING_SIZE})?|"
    r"\d+(?:\.\d+)?)(?!\s*/)(?=$|[\s,;])",
    re.IGNORECASE,
)


def _parse_query(query: str) -> dict:
    """Extract one optional budget and size, leaving the item's description."""
    price_matches = list(_PRICE_FILTER.finditer(query))
    if len(price_matches) > 1:
        raise ValueError("Specify only one budget, for example 'under $30'.")

    description = _PRICE_FILTER.sub(" ", query)
    # A leftover filter keyword means its value was missing or malformed.
    if re.search(r"\bunder\b", description, re.IGNORECASE):
        raise ValueError("Use a numeric budget, for example 'under $30'.")

    max_price = None
    if price_matches:
        max_price = float(price_matches[0].group("price"))
        if not math.isfinite(max_price) or max_price < 0:
            raise ValueError("Budget must be a finite, non-negative amount.")

    size_matches = list(_SIZE_FILTER.finditer(description))
    if len(size_matches) > 1:
        raise ValueError("Specify only one size, for example 'size M'.")

    description = _SIZE_FILTER.sub(" ", description)
    if re.search(r"\bsize\b", description, re.IGNORECASE):
        raise ValueError(
            "Use a supported size, such as 'size M', 'size W30', or 'size US 8'."
        )

    size = None
    if size_matches:
        # Normalize separators as well as case so 's / m' matches a listing's S/M.
        size = " ".join(size_matches[0].group("size").upper().split())
        size = re.sub(r"\s*/\s*", "/", size)

    # Request phrases should not add common words such as 'for' to search scores.
    description = re.sub(
        r"^\s*(?:looking\s+for|find(?:\s+me)?|show(?:\s+me)?)\s+(?:an?\s+)?",
        "",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"[\s,;]+", " ", description).strip()
    if not re.search(r"[a-z0-9]", description, re.IGNORECASE):
        raise ValueError("Describe an item to search for, for example 'graphic tee'.")

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    Regex parsing rejects invalid filters before any tool runs. Each loop
    iteration performs one stage: search, outfit, or caption. Tool results
    are saved to the session and read from it by the next stage.

    An empty search sets an actionable error and stops before either model
    tool runs. The iteration guard raises if the configured limit is exceeded.

    Unit 4 adds trace.step() calls and a handler for ModelUnavailable.
    """
    session = new_session(query, wardrobe)

    try:
        session["parsed"] = _parse_query(session["query"])
    except ValueError as error:
        # Invalid constraints should never silently become an unfiltered search.
        session["error"] = str(error)
        return session

    for count, stage in enumerate(("search", "outfit", "caption"), start=1):
        # Check before executing so no tool runs beyond the configured limit.
        trace.check_iterations(count)

        if stage == "search":
            session["search_results"] = search_listings(**session["parsed"])
            if not session["search_results"]:
                # No selected item exists, so both model stages must be skipped.
                session["error"] = (
                    "No matching listings. Try different keywords, another size, "
                    "or a higher budget."
                )
                return session
            session["selected_item"] = session["search_results"][0]

        elif stage == "outfit":
            session["outfit_suggestion"] = suggest_outfit(
                session["selected_item"], session["wardrobe"]
            )

        else:
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
