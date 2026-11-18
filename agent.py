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
import time
import uuid
from datetime import datetime, timezone

import trace
import config
import generate
import run_log
from tools import suggest_outfit, create_fit_card
from generate import ModelUnavailable, EmptyModelResponse, QuotaGuard
import mcp_client

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
        "error_stage": None,
        "error_code": None,
        "status": "running",
        "steps": [],
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def _run_tool(session, stage, name, tool, args, inputs, trace_enabled):
    """Record a tool attempt, including one that raises before returning."""
    started = time.perf_counter()
    event = {"stage": stage, "tool": name, "status": "completed"}
    try:
        result = tool(*args)
    except Exception as exc:
        event.update(status="failed", error_type=type(exc).__name__)
        if trace_enabled:
            trace.step(name, inputs=inputs, returned={"error": str(exc)},
                       note=f"{stage} failed; stopping with completed work preserved")
        raise
    else:
        if trace_enabled:
            note = ""
            if stage == "search":
                note = ("branch: use the first ranked listing for the outfit" if result
                        else "branch: empty search, stopping before outfit and caption")
            trace.step(name, inputs=inputs, returned=result, note=note)
        return result
    finally:
        event["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        session["steps"].append(event)


def run_agent(query: str, wardrobe: dict, *, trace_enabled: bool = False) -> dict:
    """Run the existing workflow, returning completed work on model failure.

    Expected provider failures are represented by error/error_code/error_stage.
    Unexpected programming errors still raise, rather than becoming false
    successes. The model adapter owns retries; the agent never retries a tool.
    """
    trace.start_trace()
    session = new_session(query, wardrobe)
    session["run_id"] = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    tokens_before = generate.token_counts()
    calls_before = generate.call_count()
    try:
        return _run_session(session, trace_enabled)
    except Exception as error:
        # Log programming/transport failures too, while preserving their exception.
        session.update(status="failed", error=f"{type(error).__name__}: {error}",
                       error_code="unexpected_error")
        if session["steps"] and session["steps"][-1]["status"] == "failed":
            session["error_stage"] = session["steps"][-1]["stage"]
        raise
    finally:
        session["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        tokens_after = generate.token_counts()
        session["usage"] = {
            "model_calls": generate.call_count() - calls_before,
            "tokens": {key: tokens_after[key] - tokens_before[key] for key in tokens_before},
            "cache_enabled": config.CACHE_ENABLED,
            "model": config.MODEL,
        }
        run_log.append({
            "schema_version": 1,
            "timestamp": timestamp,
            "run_id": session["run_id"],
            "input": {"query": query, "wardrobe": wardrobe},
            "output": {key: session[key] for key in (
                "selected_item", "outfit_suggestion", "fit_card", "error",
                "error_stage", "error_code",
            )},
            "status": session["status"],
            "duration_ms": session["duration_ms"],
            "steps": session["steps"],
            "usage": session["usage"],
        })


def _run_session(session, trace_enabled):
    try:
        session["parsed"] = _parse_query(session["query"])
    except ValueError as error:
        session.update(error=str(error), error_stage="parse",
                       error_code="invalid_query", status="rejected")
        return session

    stage = "search"
    try:
        for count, stage in enumerate(("search", "outfit", "caption"), start=1):
            trace.check_iterations(count)
            if stage == "search":
                session["search_results"] = _run_tool(
                    session, stage, "search_listings (via MCP)", mcp_client.call_tool,
                    ("search_listings", session["parsed"]), session["parsed"], trace_enabled,
                )
                if not session["search_results"]:
                    session.update(
                        error="No matching listings. Try different keywords, another size, or a higher budget.",
                        error_stage="search", error_code="no_matches", status="no_matches",
                    )
                    return session
                session["selected_item"] = session["search_results"][0]
            elif stage == "outfit":
                session["outfit_suggestion"] = _run_tool(
                    session, stage, "suggest_outfit", suggest_outfit,
                    (session["selected_item"], session["wardrobe"]),
                    {"new_item": session["selected_item"], "wardrobe": session["wardrobe"]},
                    trace_enabled,
                )
            else:
                session["fit_card"] = _run_tool(
                    session, stage, "create_fit_card", create_fit_card,
                    (session["outfit_suggestion"], session["selected_item"]),
                    {"outfit": session["outfit_suggestion"], "new_item": session["selected_item"]},
                    trace_enabled,
                )
    except (ModelUnavailable, TimeoutError, QuotaGuard) as error:
        code = ("empty_model_response" if isinstance(error, EmptyModelResponse) else
                "model_timeout" if isinstance(error, TimeoutError) else
                "quota_exceeded" if isinstance(error, QuotaGuard) else "model_unavailable")
        session.update(
            error=f"{stage.capitalize()} generation failed. {error} Try again when the model is available.",
            error_stage=stage, error_code=code, status="failed",
        )
        return session

    session["status"] = "completed"
    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    """Show completed work even when a later stage failed."""
    item = session["selected_item"]
    if item is not None:
        print(f"  Found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    if session["outfit_suggestion"] is not None:
        print(f"  Outfit:   {session['outfit_suggestion']}")
    if session["fit_card"] is not None:
        print(f"  Fit card: {session['fit_card']}")
    if session["error"]:
        print(f"  Stopped:  {session['error']}")


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
