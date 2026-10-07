# FitFindr

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, every
> command, and what to do when something breaks.
>
> Once `python test.py` passes:
>
> ```bash
> python app.py listings --full -n 6      # read the data (Milestone 1)
> python app.py fields                    # what you can filter on
> python app.py ask 'vintage graphic tee under $30'
> ```
>
> All three tools are stubs, so that last command will do nothing useful yet.
> That's the starting position.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     HOW TO USE THIS FILE

     This is your submission. Fill each section in as you finish the milestone
     it belongs to — don't leave it all to the end.

     Unit 3 asks for the first five sections. Unit 4 adds the five below them.
     Leave the unit 4 sections alone until then; they're here so you know
     what's coming.

     Everything is pasted as TEXT. No screenshots, no images, no video links.
     A typed block of output gets full credit; a picture of the same output
     gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 3 — THE BUILD ═══════════════════════ -->

## What This Does

<!-- Three or four sentences: what a user asks for, and what they get back. -->



---

## Tool Inventory

<!-- Four lines per tool. This is worth 2 points and it's the single most
     common place students lose them.

     "Returns a list" earns NOTHING. The description has to say what is IN
     the list.

     The empty case isn't optional either — it's the thing your loop branches
     on, and if you don't decide it here you'll discover it as a crash in
     Milestone 5. -->

### `search_listings`

- **What it does:** Searches the local mock listings, applies optional size and budget filters, and ranks the remaining items by keyword overlap with the requested description without calling a model.
- **Inputs:** `description` (`str`) contains search keywords; `size` (`str | None`, default `None`) is an optional size filter; `max_price` (`float | None`, default `None`) is an optional inclusive price ceiling in dollars. `None` skips that filter. Size matching is case-insensitive: ignore parenthesized fit notes, match complete slash-separated sizes (`M` matches `S/M`, but `L` does not match `XL`), accept `One Size` for one-size listings, match a waist such as `W30` against `W30 L30`, and accept either `8` or `US 8` for shoe size `US 8` without matching `US 8.5`.
- **Returns:** A `list[dict]` of at most `config.SEARCH_RESULT_LIMIT` listings. Each dictionary contains `id` (`str`), `title` (`str`), `description` (`str`), `category` (`str`), `style_tags` (`list[str]`), `size` (`str`), `condition` (`str`), `price` (`float`), `colors` (`list[str]`), `brand` (`str | None`), and `platform` (`str`). Score each listing by the number of distinct, case-insensitive alphanumeric query words found in its title, description, or style tags; discard zero-score listings, sort highest score first, and preserve dataset order for ties.
- **When it has nothing:** Returns `[]` when no listing passes the filters and has a positive keyword score, including when the description contains no searchable words; never returns `None` for no matches.

### `suggest_outfit`

- **What it does:** Calls the model through `generate()` to suggest one or two outfits combining the selected listing with pieces in the user's wardrobe.
- **Inputs:** `new_item` (`dict`) is one complete listing returned by `search_listings`; `wardrobe` (`dict`) has an `items` key containing a `list[dict]`, where each wardrobe item has `id` (`str`), `name` (`str`), `category` (`str`), `colors` (`list[str]`), `style_tags` (`list[str]`), and optional `notes` (`str | None`). The `items` list may be empty.
- **Returns:** A non-empty `str` describing one or two outfits, naming the selected item and the wardrobe pieces used, with a brief explanation of how the pieces work together. The prompt uses available item details without assuming a brand exists.
- **When it has nothing:** With `wardrobe["items"] == []`, asks the model for general styling advice for the selected item and returns that advice as a non-empty `str`; suggested pieces are ideas, not claims about clothes the user owns.

### `create_fit_card`

- **What it does:** Calls the model through `generate()` to turn the selected listing and outfit suggestion into a short caption someone could post about their find.
- **Inputs:** `outfit` (`str`) is the text returned by `suggest_outfit`; `new_item` (`dict`) is the same complete listing used for that suggestion.
- **Returns:** A non-empty `str` containing a two-to-four-sentence caption that mentions the item, its price in dollars, and its platform once each, and describes the outfit's specific style. The prompt includes the outfit and item details, omits an unknown brand, and asks for wording tailored to the input rather than a fixed caption.
- **When it has nothing:** If `outfit` is empty or contains only whitespace, returns the string `Cannot create a fit card without an outfit suggestion. Try generating an outfit first.` without calling the model.

---

## Planning Loop

<!-- Your branch rule, stated as a rule — the condition AND both paths — plus
     the file and function that holds it.

     Like this:
       "If search_listings returns an empty list, put a message in the session
        and stop. Otherwise take the first result and go to suggest_outfit."
        — agent.py::run_agent

     The grader checks your code against what you claim here, so the file and
     function have to be real. -->

**Branch rule:** If `search_listings` returns `[]`, set `session["error"]` to `No matching listings. Try different keywords, another size, or a higher budget.` and return the session before calling either remaining tool. Otherwise, save the first result in `session["selected_item"]`, call `suggest_outfit` using that item and `session["wardrobe"]`, save its result in `session["outfit_suggestion"]`, then call `create_fit_card` using that saved suggestion and the same selected item, save its result in `session["fit_card"]`, and return the session. This is the planned rule to implement in Milestone 5.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** <!-- regex, string splitting, or asking the model — say which -->

**What moves through the session:** <!-- which fields, in what order -->

---

## Sample Run

<!-- Two things go here.

     1. One FULL query and its output, pasted as text.
     2. Your three per-tool terminal tests — the command and what it printed. -->

**One full query**

```
$ python app.py ask '...'

```

**The three tools, tested one at a time**

Run these commands from the project directory using its virtual environment. Each block contains the actual terminal output; model responses have their whitespace joined into one line for display.

```text
$ .venv/bin/python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
[{'id': 'lst_002', 'title': 'Y2K Baby Tee — Butterfly Print', 'description': 'Super cute early 2000s baby tee with butterfly graphic. Fitted crop length. Tag says medium but fits like a small.', 'category': 'tops', 'style_tags': ['y2k', 'vintage', 'graphic tee', 'cottagecore'], 'size': 'S/M', 'condition': 'excellent', 'price': 18.0, 'colors': ['white', 'pink', 'purple'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_006', 'title': 'Graphic Tee — 2003 Tour Bootleg Style', 'description': 'Vintage-style bootleg tee with faded graphic. Slightly boxy fit. 100% cotton, soft and worn-in.', 'category': 'tops', 'style_tags': ['graphic tee', 'vintage', 'grunge', 'streetwear', 'band tee'], 'size': 'L', 'condition': 'good', 'price': 24.0, 'colors': ['black'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_017', 'title': 'Mesh Long-Sleeve Top — Black', 'description': 'Sheer black mesh long-sleeve. Great for layering under a graphic tee or over a bralette. Stretchy material, fits true to size.', 'category': 'tops', 'style_tags': ['y2k', 'grunge', 'goth', 'layering'], 'size': 'S/M', 'condition': 'excellent', 'price': 15.0, 'colors': ['black'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_033', 'title': 'Vintage Band Tee — Faded Grey', 'description': 'Faded grey band-style tee with distressed graphic. Crew neck. Fits boxy. Well-loved but no holes or major damage.', 'category': 'tops', 'style_tags': ['vintage', 'grunge', 'band tee', 'graphic tee', 'streetwear'], 'size': 'L', 'condition': 'fair', 'price': 19.0, 'colors': ['grey', 'charcoal'], 'brand': None, 'platform': 'depop'}, {'id': 'lst_011', 'title': 'Low-Rise Cargo Pants — Khaki', 'description': 'Y2K era low-rise cargo pants. Lots of pockets. Khaki color, slightly distressed at the hems. Great for layering with a long tee.', 'category': 'bottoms', 'style_tags': ['y2k', 'cargo', '2000s', 'streetwear'], 'size': 'W29', 'condition': 'fair', 'price': 27.0, 'colors': ['khaki', 'tan'], 'brand': None, 'platform': 'poshmark'}, {'id': 'lst_015', 'title': 'Vintage Graphic Hoodie — Faded Black', 'description': 'Faded black pullover hoodie with barely-visible vintage graphic on the chest. Cozy interior. Some pilling but adds to the worn-in look.', 'category': 'tops', 'style_tags': ['vintage', 'grunge', 'graphic', 'streetwear'], 'size': 'L', 'condition': 'fair', 'price': 26.0, 'colors': ['black', 'charcoal'], 'brand': None, 'platform': 'depop'}]
```

```text
$ .venv/bin/python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(' '.join(suggest_outfit(load_listings()[1], get_example_wardrobe()).split()))"
Here is an outfit featuring the selected thrifted item, using only your existing wardrobe pieces: ### **Outfit: Y2K Streetwear Contrast** * **Thrifted Item:** Y2K Baby Tee — Butterfly Print * **Wardrobe Pieces Used:** * Baggy straight-leg jeans, dark wash (`w_001`) * Vintage black denim jacket (`w_006`) * Chunky white sneakers (`w_007`) * Black crossbody bag (`w_010`) **Why it works:** * **Colors:** The white, pink, and purple in the butterfly graphic pop against the dark blue and indigo of the jeans, while the black denim jacket and bag ground the pastel tones for a balanced look. The white sneakers tie back to the white base of the baby tee. * **Fit:** This outfit plays on the classic Y2K proportion-play of tight-over-loose. The fitted, cropped nature of the baby tee contrasts sharply with the high-waisted, baggy straight-leg jeans, creating a flattering silhouette. The slightly cropped black denim jacket mirrors the baby tee's length while adding structure. * **Style:** The vintage, graphic-heavy Y2K aesthetic of the tee blends effortlessly with the streetwear elements of the baggy denim and chunky sneakers, resulting in a cohesive, era-inspired look.
```

```text
$ .venv/bin/python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(' '.join(create_fit_card('Y2K butterfly baby tee with baggy dark-wash jeans, a vintage black denim jacket, chunky white sneakers, and a black crossbody bag', load_listings()[1]).split()))"
Channeling full early-2000s mallrat energy with these baggy dark-wash jeans and this little butterfly baby tee. I scored it on depop for $18.00 and it honestly completes my whole denim jacket rotation.
```

---

## How I Used AI

<!-- Two specific moments. What you asked, what came back, what you changed.

     "I used Claude to help me code" is not enough.

     "I gave Claude my search_listings spec. It returned None on no match
     instead of an empty list, so I changed it" is the level we want. -->

**Moment 1**

- *What I asked for:*
- *What came back:*
- *What I changed:*

**Moment 2**

- *What I asked for:*
- *What came back:*
- *What I changed:*

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════

     Don't fill these in during unit 3.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Run Log — Before

<!-- Five criteria, five tries each, in this exact format.

     Five, because your criteria are written out of five. Mark each try PASS
     or FAIL, count the passes, and read that count against your target — a
     row targeting 4 of 5 with three PASS cells is MISSED (3/5).

     `python run_eval.py --label before` runs everything and writes the table
     into results/. Paste it here and fill in the verdicts. -->

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Real output from one try**, pasted as text, naming the file and function
that produced it:

```

```

---

## Verdicts and Diagnoses

<!-- MET or MISSED per criterion against LAST UNIT's target, plus a sentence on
     how you decided.

     Then, for every miss: which of the four places it happened — a tool, the
     loop's branch, the session, or the model's output — AND the mechanism.

     Not a diagnosis:  "The fit card was bad."
     A diagnosis:      "The fit card criterion missed on 2 of 5 items. Both had
                        an empty brand field. My prompt puts the brand in the
                        first sentence, so the card opened with a blank and read
                        like a fragment. The tool worked; the prompt assumed a
                        field that isn't always there."

     Look for a pattern. Three misses on the same tool is one problem, not
     three. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

**Diagnoses**



---

## Loop Trace

<!-- One full run, printed step by step, with the MCP call visible in it.

     `python app.py ask '...' --trace` once you've added the trace.step()
     calls in Milestone 2.

     Worth pasting BOTH the happy path and the empty-search path. The empty
     one should be visibly shorter, because it stops. If your two traces are
     the same length, your branch isn't working — and this is the fastest way
     anyone will ever find that out. -->

**Happy path**

```

```

**Empty search**

```

```

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:**

**Which failure it was meant to fix:**

### Run Log — After

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it made things worse, say that. Honestly reported, that earns full
     credit and is more interesting than one that worked. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [ ] criteria.md has five numbered criteria, each with a target
       [ ] Each criterion has a reason underneath it
       [ ] All five unit 3 sections above have real content
       [ ] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [ ] Planning Loop names the branch rule and agent.py::run_agent
       [ ] Sample Run: one full query plus the three per-tool tests, as text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [ ] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
