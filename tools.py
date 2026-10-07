"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three tools are implemented below. Search runs locally; the other two
call the model through the shared generate() adapter.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import json
import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _keywords(text: str) -> set[str]:
    """Extract unique, case-insensitive words for search scoring."""
    # Whole words avoid partial matches; the set counts repeated words only once.
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _normalize_size(size: str) -> str:
    """Ignore parenthetical notes, capitalization, and extra whitespace."""
    # Notes such as "(oversized)" describe fit without changing the labeled size.
    size_without_notes = re.sub(r"\([^)]*\)", "", size)
    return " ".join(size_without_notes.casefold().split())


def _matches_size(listed_size: str, requested_size: str) -> bool:
    """Compare a listing size with an already normalized requested size."""
    listed_size = _normalize_size(listed_size)
    if not requested_size:
        return False

    if requested_size == listed_size:
        return True

    # A combined size such as S/M matches either S or M, but XL does not match L.
    combined_sizes = [part.strip() for part in listed_size.split("/")]
    if requested_size in combined_sizes:
        return True

    # Waist sizes can appear alongside a length, such as W32 L30.
    if re.fullmatch(r"w\d+", requested_size):
        return requested_size in listed_size.split()

    # Accept requests such as "9" or "US 9", but require a US label on the listing
    # so a numeric request does not accidentally match part of a waist size.
    requested_shoe_size = re.fullmatch(r"(?:us\s+)?(\d+(?:\.\d+)?)", requested_size)
    listed_shoe_size = re.fullmatch(r"us\s+(\d+(?:\.\d+)?)", listed_size)
    if requested_shoe_size is None or listed_shoe_size is None:
        return False

    # Compare numeric values so "9" and "9.0" refer to the same shoe size.
    return float(requested_shoe_size.group(1)) == float(listed_shoe_size.group(1))


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    Steps:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    query_words = _keywords(description)
    # Empty or punctuation-only queries cannot produce a keyword match.
    if not query_words:
        return []

    # Normalize the requested size once, since it is reused for every listing.
    requested_size = _normalize_size(size) if size is not None else None
    scored_listings = []

    for listing in load_listings():
        # Apply mandatory filters before doing the text processing for scoring.
        # Using > keeps listings priced exactly at max_price eligible.
        if max_price is not None and listing["price"] > max_price:
            continue
        if requested_size is not None and not _matches_size(
            listing["size"], requested_size
        ):
            continue

        searchable_text = " ".join(
            [listing["title"], listing["description"], *listing["style_tags"]]
        )
        listing_words = _keywords(searchable_text)
        # Each distinct query word found in the title, description, or tags adds
        # one point. Exclude zero-score listings so unrelated items never appear.
        score = len(query_words & listing_words)
        if score > 0:
            scored_listings.append((score, listing))

    # Highest overlap wins; Python's stable sort preserves source order for ties.
    scored_listings.sort(key=lambda match: match[0], reverse=True)
    top_matches = scored_listings[:config.SEARCH_RESULT_LIMIT]
    # Scores are internal ranking data; callers receive only the listing dicts.
    return [listing for _, listing in top_matches]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_listing(listing: dict) -> str:
    """Format the known listing details for use in either model prompt."""
    # Keep the original intact because the same listing is passed to both tools.
    known_details = listing.copy()
    # Omit unknown brands so the prompt contains only available information.
    if not known_details.get("brand"):
        known_details.pop("brand", None)
    return json.dumps(known_details, indent=2, ensure_ascii=False)


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    Steps:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    item_details = _format_listing(new_item)
    wardrobe_items = wardrobe["items"]

    if wardrobe_items:
        # Include names and styling details so combinations refer to owned pieces.
        wardrobe_details = json.dumps(wardrobe_items, indent=2, ensure_ascii=False)
        prompt = (
            "Suggest one or two outfits featuring the selected thrifted item. "
            "Name the item and the wardrobe pieces used, and briefly explain "
            "how their colors, fit, and style work together. Use only the listed "
            "wardrobe pieces as companions; do not invent clothes the user owns.\n\n"
            f"Selected item:\n{item_details}\n\n"
            f"Owned wardrobe pieces:\n{wardrobe_details}"
        )
    else:
        # With no owned pieces to reference, ask for ideas without claiming ownership.
        prompt = (
            "The user's wardrobe is empty. Give one or two general outfit ideas "
            "featuring the selected thrifted item, with a brief explanation of "
            "colors, fit, and style. Present companion pieces as suggestions, "
            "not as clothes the user already owns.\n\n"
            f"Selected item:\n{item_details}"
        )

    # The shared adapter handles pacing, caching, and model errors.
    response = generate(prompt).strip()
    # A blank model response still needs a useful, non-empty result for the caller.
    return response or "No outfit suggestion was generated. Please try again."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    Steps:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    outfit_description = outfit.strip()
    # Stop before calling the model when there is no outfit to base the caption on.
    if not outfit_description:
        return (
            "Cannot create a fit card without an outfit suggestion. "
            "Try generating an outfit first."
        )

    item_details = _format_listing(new_item)
    # Include the outfit for a specific vibe and an explicit dollar price so the
    # caption can mention the find accurately without guessing its details.
    prompt = (
        "Write a two-to-four-sentence caption someone would actually post "
        "about this thrift find. Use a natural, personal voice and describe "
        "the outfit's specific vibe rather than writing a product description. "
        "Mention the item, its price in dollars, and its platform exactly once "
        "each. Tailor the wording to this item and outfit, and do not invent "
        "a brand or other details. Return only the caption.\n\n"
        f"Selected item:\n{item_details}\n\n"
        f"Price to mention: ${new_item['price']:.2f}\n"
        f"Platform to mention: {new_item['platform']}\n\n"
        f"Outfit suggestion:\n{outfit_description}"
    )
    response = generate(prompt).strip()
    # Preserve the non-empty return contract even if the model supplies no text.
    return response or "No fit card was generated. Please try again."
