# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**
The successful path depends on two model calls as well as the local search.
At least 4 of 5 tries requires reliable completion while allowing one failure
from an unavailable model or an unusable model response; 5 of 5 would assume
the external service always succeeds.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
This path uses local search and a Python branch, with no model call needed.
An empty list should always trigger the same stop condition, so even one call
to the next tool on this path would indicate a bug and 5 of 5 is appropriate.

---

## 3. The selected item reaches the outfit tool unchanged in identity

Given a query that matches at least one listing, the `new_item["id"]` actually
received by `suggest_outfit` equals `session["selected_item"]["id"]` — in
5 of 5 tries. Record the received argument at the tool entry or intercept it
in a test; inspecting only the final session is not enough. A try that never
reaches `suggest_outfit` fails this criterion.

**Why this target:**

Passing the selected item from the session into a function is controlled by
Python code, not by the model. There is no acceptable variation in which item
gets passed, so anything below 5 of 5 would permit a state-handling bug.

---

## 4. The fit card includes the item, price, and platform once each

For the same selected listing, the generated fit card mentions its full
`title`, correct dollar price, and `platform` exactly once each — in at least
4 of 5 tries, with caching disabled. Match the title and platform
case-insensitively. Count the price as a dollar amount equal to the listing's
price (`$24` and `$24.00` both count for `24.0`); a conflicting dollar amount
fails the try. A missing or empty fit card also fails.

**Why this target:**

These details let a reader identify the find and know its cost and source.
The model writes the caption at temperature 0.9, so it may omit or repeat a
detail even when the prompt requests it; 4 of 5 requires consistent compliance
without assuming every generated caption follows the instructions perfectly.

---

## 5. Search respects the price ceiling without returning only empty results

Run `search_listings` once for each description `graphic tee`, `flannel`,
`tank`, `belt`, and `vintage`, with `max_price=30.0` and `size=None`.
Each search returns at least one listing, and every returned listing has
`price <= 30.0` — in 5 of 5 searches. An empty result fails, because each of
these descriptions has a matching listing within the budget in the starter
dataset.

**Why this target:**

The price filter is a deterministic numeric comparison on local data, so it
should never return an item over budget. Requiring a non-empty result also
prevents an unfinished search that always returns `[]` from passing; there
is no reason to allow a failure among these five known-match searches.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
