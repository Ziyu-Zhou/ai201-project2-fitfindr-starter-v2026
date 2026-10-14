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
> The three tools and planning loop are implemented. The last command searches
> the mock listings, suggests an outfit, and generates a fit card.
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

FitFindr lets a user describe a thrift find and optionally specify a size and budget, such as `graphic tee under $30, size M`.
It searches 40 local mock listings, filters by those constraints, and selects the item with the most matching keywords.
The model suggests an outfit using the user's saved wardrobe, or general styling ideas when the wardrobe is empty, then writes a short caption about the find, its price, platform, and outfit.
If the search finds nothing or the filters are invalid, the agent stops with a message explaining what the user can change.

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

**Branch rule:** If `search_listings` returns `[]`, set `session["error"]` to `No matching listings. Try different keywords, another size, or a higher budget.` and return the session before calling either remaining tool. Otherwise, save the first result in `session["selected_item"]`, call `suggest_outfit` using that item and `session["wardrobe"]`, save its result in `session["outfit_suggestion"]`, then call `create_fit_card` using that saved suggestion and the same selected item, save its result in `session["fit_card"]`, and return the session. The loop runs one stage per iteration and calls `trace.check_iterations(count)` before each tool; exceeding `config.MAX_ITERATIONS` raises before the next tool runs.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** `agent.py::_parse_query` uses case-insensitive regex, without a model call. It extracts an optional budget such as `under $30` or `under 30.50` and an optional size such as `size M`, `in size S/M`, `size W30`, `size W30 L30`, `size US 8.5`, `size 8`, or `size One Size`. Sizes are normalized to uppercase, with spaces around `/` removed. The filters, separator commas and semicolons, and leading request phrases such as `looking for a` or `find me a` are removed from the description before search. A budget must be a finite, non-negative number without thousands separators. Invalid, missing, or repeated filter values and an empty description set `session["error"]` and stop before any tool runs. For example, `graphic tee under $30, size M` becomes `{"description": "graphic tee", "size": "M", "max_price": 30.0}`.

**What moves through the session:** `new_session` stores the original `query` and `wardrobe`. Parsing fills `parsed`; search reads those filters and fills `search_results`; the first match becomes `selected_item`. The outfit stage reads `selected_item` and `wardrobe`, then fills `outfit_suggestion`. The caption stage reads that saved suggestion and the same `selected_item`, then fills `fit_card`. All tool results remain in the returned session for inspection. On invalid input or an empty search, `error` explains what to change, and stages that did not run keep their fields at `None`.

**Automated checks:** `.venv/bin/python -m unittest discover -s tests -v` checks query parsing, rejected filters, tool ordering, selected-item identity, the empty-search stop, the iteration limit, and an empty wardrobe without live model calls.

---

## Sample Run

<!-- Two things go here.

     1. One FULL query and its output, pasted as text.
     2. Your three per-tool terminal tests — the command and what it printed. -->

**One full query**

```text
$ .venv/bin/python app.py ask 'vintage graphic tee under $30, size M'

  Found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop

  Outfit:   Here is an outfit featuring the selected thrifted item, using only your existing wardrobe pieces:

### **Outfit: Y2K Streetwear Contrast**

* **Thrifted Item:** Y2K Baby Tee — Butterfly Print
* **Wardrobe Pieces Used:**
  * Baggy straight-leg jeans, dark wash (`w_001`)
  * Vintage black denim jacket (`w_006`)
  * Chunky white sneakers (`w_007`)
  * Black crossbody bag (`w_010`)

**Why it works:**
* **Colors:** The white, pink, and purple in the butterfly graphic pop against the dark blue and indigo of the jeans, while the black denim jacket and bag ground the pastel tones for a balanced look. The white sneakers tie back to the white base of the baby tee.
* **Fit:** This outfit plays on the classic Y2K proportion-play of tight-over-loose. The fitted, cropped nature of the baby tee contrasts sharply with the high-waisted, baggy straight-leg jeans, creating a flattering silhouette. The slightly cropped black denim jacket mirrors the baby tee's length while adding structure.
* **Style:** The vintage, graphic-heavy Y2K aesthetic of the tee blends effortlessly with the streetwear elements of the baggy denim and chunky sneakers, resulting in a cohesive, era-inspired look.

  Fit card: Balanced out this butterfly baby tee with some baggy dark denim and chunky sneakers for the ultimate tight-over-loose Y2K look. Snagged it on depop for just $18.00 and I'm obsessed with how the pink and purple graphics pop against the dark wash.

0 model calls this session, 2 served from cache
```

This CLI run reused the model responses cached during the preceding `.venv/bin/python agent.py` test.

**Early-stop examples**

```text
$ .venv/bin/python app.py ask 'designer ballgown size XXS under $5'

  No matching listings. Try different keywords, another size, or a higher budget.

0 model calls this session
```

```text
$ .venv/bin/python app.py ask 'graphic tee under $-5'

  Budget must be a finite, non-negative amount.

0 model calls this session
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

- *What I asked for:* I asked Codex to implement `suggest_outfit` and `create_fit_card`, then improve readability and add meaningful comments explaining the logic.
- *What came back:* Codex added prompts that use owned wardrobe pieces or offer general advice for an empty wardrobe. The caption tool returns an explanatory message for a blank outfit without calling the model. Both tools use the shared `generate()` adapter.
- *What I changed:* I requested the readability and comment passes. The repeated listing formatting was moved into `_format_listing`, which omits unknown brands without changing the original listing, and the empty-input branches received explanatory comments. I then asked Codex to run each tool from a terminal and paste the actual commands and outputs into **Sample Run** above.

**Moment 2**

- *What I asked for:* I asked Codex to explain Milestone 5 and the decisions involved, then approved regex parsing, explicit search/outfit/caption stages, and clear errors for invalid filters.
- *What came back:* Codex implemented `_parse_query` and `run_agent`. The loop saves each result in the session, chooses the first ranked listing, checks the iteration limit before each stage, and stops before the model tools when search returns no listings.
- *What I changed:* I chose regex so parsing would not need another model call, and accepted rejection of invalid budgets rather than silently ignoring them. I also asked why the direct `config` import was removed from `agent.py`; the iteration limit still reads `config.MAX_ITERATIONS` inside `trace.check_iterations`. Seven automated tests and the terminal runs verify parsing, state handoffs, early stops, and the iteration limit; these are checks of the build, not the five-trial Unit 4 evaluation.

**Submission repository:** [Ziyu-Zhou/ai201-project2-fitfindr-starter-v2026](https://github.com/Ziyu-Zhou/ai201-project2-fitfindr-starter-v2026). Use this same repository for Unit 4. The local Unit 3 work is complete; push the commits and submit this URL through the course submission page.

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

Executed from the project directory:

```bash
.venv/bin/python -u run_eval.py --label before
```

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. Matching query completes all three tools | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. Impossible query stops before the second tool | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. Selected item reaches the outfit tool unchanged in identity | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Fit card includes full title, price, and platform once each | 4 of 5 | FAIL | FAIL | FAIL | FAIL | FAIL | MISSED (0/5) |
| 5. Known-match searches return nonempty results within the price ceiling | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

**Evaluation protocol and evidence**

The original criteria and targets in `criteria.md` are unchanged. Each numbered
scenario ran five times with caching off and temperature 0.9. Tool-entry wrappers
in `run_eval.py::run_once` recorded the actual arguments and then called the real
implementations; they did not replace model responses. The source hashes in the
raw evidence confirm the agent, tools, prompts, and evaluation configuration
stayed fixed during the run.

For criterion 5, each try repeats the complete set of five descriptions in the
original criterion, with `size=None` and `max_price=30.0`. A try passes only when
all five searches return at least one listing and every returned price is within
the ceiling. This gives 25 actual MCP searches, with no model calls for that row.
The empty-wardrobe scenario also ran five times as an ungraded diagnostic; all
five runs returned nonempty outfit advice and a fit card.

- [Full run log](results/run_2026-10-13_224415_before.md)
- [Raw sessions, received tool arguments, results, and source hashes](results/run_2026-10-13_224415_before.json)
- Usage: **40 uncached model calls**, 30,158 prompt tokens and 7,539 output tokens.
- Every model-backed try made two live requests; the five criterion-4 captions
  were distinct. Identical search-only results are expected from deterministic data.

**Real output from one try of each criterion**

These excerpts come from the saved first try for each numbered scenario. The
report formatting is produced by `run_eval.py::write_report`; the source of each
result is named below.

**1. Full three-tool run — `agent.py::run_agent` and `tools.py::create_fit_card`**

```text
[1] search_listings (via MCP)
      in:  {description: vintage graphic tee, size: None, max_price: 30.0}
      out: 10 items: Y2K Baby Tee — Butterfly Print, Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey … +7 more
      →    branch: use the first ranked listing for the outfit
[2] suggest_outfit
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), wardrobe: {items: 10 items: {'id': 'w_001', 'name': 'Baggy straight-leg jeans, dark wash…}}
      out: Here is an outfit featuring your selected thrifted item:  ### Outfit: Y2K Streetwear Contrast  * **Selected Th…
[3] create_fit_card
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), outfit: Here is an outfit featuring your selected thrifted item:  ### Outfit: Y2K Streetwear Contrast  * **Selected Th…}
      out: Found my absolute dream Y2K baby tee with the cutest butterfly graphic and had to style it right away with bag…

Fit card:
Found my absolute dream Y2K baby tee with the cutest butterfly graphic and had to style it right away with baggy denim and chunky sneakers. It gives major early 2000s streetwear energy and fits like an absolute dream. Snagged this gem for just $18.00 and I'm honestly never taking it off. Listing it over on depop if anyone else needs a little nostalgia in their wardrobe!
```

**2. Empty-search stop — `agent.py::run_agent`**

```text
[1] search_listings (via MCP)
      in:  {description: designer ballgown, size: XXS, max_price: 5.0}
      out: [] (empty)
      →    branch: empty search, stopping before outfit and caption

No matching listings. Try different keywords, another size, or a higher budget.
```

**3. Actual received item — `run_eval.py::run_once`, intercepting `tools.py::suggest_outfit`**

```text
- selected_item: lst_002 — Y2K Baby Tee — Butterfly Print ($18.0, depop)
search_listings (via MCP); returned successfully
suggest_outfit; received new_item.id=lst_002; returned successfully
create_fit_card; received new_item.id=lst_002; returned successfully
```

The captured outfit-tool entry ID equals the final selected-item ID in every try.

**4. Caption details — `tools.py::create_fit_card`**

```text
Obsessed with how the pink and purple butterfly graphic pops against this oversized dark denim. Scored this little baby tee for $18.00 and it balances out baggy jeans so well. Just listed it on depop if anyone else wants to lean into the nostalgic streetwear look!
```

This try mentions `$18.00` and `depop` once each, but does not include the full
title `Y2K Baby Tee — Butterfly Print`. The same full-title omission occurs in all
five tries, so all five fail under the original criterion.

**5. Budget searches — `mcp_server.py::search_listings`, delegating to `tools.py::search_listings`**

```text
{'description': 'graphic tee', 'size': None, 'max_price': 30.0}
lst_002: Y2K Baby Tee — Butterfly Print — $18.00
lst_006: Graphic Tee — 2003 Tour Bootleg Style — $24.00
lst_017: Mesh Long-Sleeve Top — Black — $15.00
lst_033: Vintage Band Tee — Faded Grey — $19.00
lst_011: Low-Rise Cargo Pants — Khaki — $27.00
lst_015: Vintage Graphic Hoodie — Faded Black — $26.00

{'description': 'flannel', 'size': None, 'max_price': 30.0}
lst_003: Oversized Flannel Shirt — Plaid Red/Black — $22.00

{'description': 'tank', 'size': None, 'max_price': 30.0}
lst_023: Crochet Halter Top — Cream — $22.00

{'description': 'belt', 'size': None, 'max_price': 30.0}
lst_014: Leather Belt — Brown, Braided — $12.00

{'description': 'vintage', 'size': None, 'max_price': 30.0}
lst_002: Y2K Baby Tee — Butterfly Print — $18.00
lst_003: Oversized Flannel Shirt — Plaid Red/Black — $22.00
lst_006: Graphic Tee — 2003 Tour Bootleg Style — $24.00
lst_012: Oversized Crewneck Sweatshirt — Vintage Navy — $20.00
lst_013: 90s Silk Slip Dress — Floral, Midi Length — $30.00
lst_014: Leather Belt — Brown, Braided — $12.00
lst_015: Vintage Graphic Hoodie — Faded Black — $26.00
lst_016: High-Waisted Denim Shorts — Cutoff — $24.00
lst_020: Henley Long Sleeve — Washed Burgundy — $16.00
lst_021: Straight Leg Khaki Trousers — Olive — $29.00

```

Every search is nonempty; the highest returned price is $30.00. All five trials
satisfy both parts of the original budget criterion.

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
| 1 | A matching query completes all three tools | 4 of 5 | MET (5/5) | Every try completed search, outfit, and caption in order, returned a nonempty fit card, and had no session error or exception. |
| 2 | An impossible query stops before the second tool | 5 of 5 | MET (5/5) | Every try returned an empty search, recorded only the MCP search call, and told the user to change keywords, size, or budget; neither model tool ran. |
| 3 | The selected item reaches the outfit tool unchanged in identity | 5 of 5 | MET (5/5) | The ID captured at the actual `suggest_outfit` entry was `lst_002` in every try, equal to `session["selected_item"]["id"]`; the tool was reached in all five tries. |
| 4 | The fit card includes the item, price, and platform once each | 4 of 5 | MISSED (0/5) | Every caption mentioned the correct $18.00 price and depop once, but none contained the full title `Y2K Baby Tee — Butterfly Print`, so each failed one required part. |
| 5 | Search respects the price ceiling without returning only empty results | 5 of 5 | MET (5/5) | In every trial, all five originally specified descriptions returned at least one listing and every returned price was at most $30.00, giving 25 compliant MCP searches. |

**Diagnoses**

**Criterion 4 — model output at the caption step, `tools.py::create_fit_card`.**
All five misses follow the same pattern for the same selected listing: the model
paraphrases the item as a "little baby tee," "butterfly baby tee," or "early
2000s baby tee" instead of reproducing its complete listing title. The five
captions are different, and each try made two uncached model requests, so this
is a repeated omission across fresh outputs.

| Try | Full title occurrences | Correct dollar amount occurrences | Platform occurrences | Result |
|---|---|---|---|---|
| 1 | 0 | 1 | 1 | FAIL |
| 2 | 0 | 1 | 1 | FAIL |
| 3 | 0 | 1 | 1 | FAIL |
| 4 | 0 | 1 | 1 | FAIL |
| 5 | 0 | 1 | 1 | FAIL |

**Mechanism:** The caption prompt says "Mention the item, its price in dollars,
and its platform exactly once each." It includes the complete title inside the
selected-item JSON, but does not explicitly require copying that title verbatim.
Describing a butterfly tee satisfies the broad instruction to mention the item
while missing the criterion's exact full-title requirement. The tool then returns
`generate(prompt).strip()` without checking whether the required title appears.
The likely cause is this gap between the prompt's item-description instruction
and the criterion's literal-title contract; the observed failure is in the
model's caption output.

The recorded arguments localize the problem: `create_fit_card` received the
correct title `Y2K Baby Tee — Butterfly Print` in all five tries, together with
the outfit saved in the session. `_format_listing` preserves that title when it
builds the prompt. The loop reached all three stages, and the item identity
remained `lst_002`. The title was available at the caption step; it was omitted
from the generated text. These five misses therefore indicate one recurring
caption problem. The evidence covers this listing and these trials; it does not
establish how often the omission occurs for other listings.

Evidence: the **fit card includes full title, price, and platform once** scenario
in the [full baseline log](results/run_2026-10-13_224415_before.md), with the actual
caption-tool arguments and complete responses in the
[raw evidence](results/run_2026-10-13_224415_before.json).

**Verdict challenge:** The strongest case for calling criterion 4 MET is that
the captions describe the right butterfly tee and include the correct price and
platform, so a reader could understand the find. That argument would fit a
criterion requiring only a recognizable description. The original criterion
explicitly requires the full title exactly once, with case-insensitive matching.
All five have zero matches, so the MISSED verdict holds. Criterion 1 can still
be MET because it measures completion of the three-tool path; criterion 4
measures the resulting caption's specific content.

**Criterion revisions:** None. Criterion 4 is measurable and the omission can
be identified directly in each response. The original wording and targets stay
in place. The next improvement should address the caption's exact-title
instruction and then be measured with the same scenarios and scoring rules.

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

Run from the project directory. This is the actual trace printed by
`agent.py::run_agent`; the CLI also printed the outfit and fit card shown in
**Sample Run** above. The model responses came from the build cache, while the
search still ran through MCP.

```text
$ .venv/bin/python app.py ask 'vintage graphic tee under $30, size M' --trace
[1] search_listings (via MCP)
      in:  {description: vintage graphic tee, size: M, max_price: 30.0}
      out: 8 items: Y2K Baby Tee — Butterfly Print, Mesh Long-Sleeve Top — Black, 90s Silk Slip Dress — Floral, Midi Length … +5 more
      →    branch: use the first ranked listing for the outfit
[2] suggest_outfit
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), wardrobe: {items: 10 items: {'id': 'w_001', 'name': 'Baggy straight-leg jeans, dark wash…}}
      out: Here is an outfit featuring the selected thrifted item, using only your existing wardrobe pieces:  ### **Outfi…
[3] create_fit_card
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), outfit: Here is an outfit featuring the selected thrifted item, using only your existing wardrobe pieces:  ### **Outfi…}
      out: Balanced out this butterfly baby tee with some baggy dark denim and chunky sneakers for the ultimate tight-ove…

0 model calls this session, 2 served from cache
```

**Empty search**

```text
$ .venv/bin/python app.py ask 'designer ballgown size XXS under $5' --trace
[1] search_listings (via MCP)
      in:  {description: designer ballgown, size: XXS, max_price: 5.0}
      out: [] (empty)
      →    branch: empty search, stopping before outfit and caption

  No matching listings. Try different keywords, another size, or a higher budget.

0 model calls this session
```

The empty-search trace has one tool call because the loop stops before
`suggest_outfit` and `create_fit_card`. Trace calls run only when `--trace` is
requested, and each run resets the step numbering.

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:** Rewrote only the caption prompt in
`tools.py::create_fit_card`. The original instruction to "mention the item"
became "Include the exact full listing title once, verbatim. Do not shorten
or paraphrase it." The prompt also supplies an explicit
`Exact title to include: ...` line using `new_item["title"]`. The caption still
asks for the correct dollar price and platform once each and a natural
description of the outfit.

**Which failure it was meant to fix:** Criterion 4 passed 0 of 5 baseline tries
because the model paraphrased the item instead of copying its full title, even
though the correct title reached the caption tool in every try. The change makes
the exact-title requirement explicit at that same step.

The after-run uses the same scenarios, original criteria and targets, model,
temperature 0.9, iteration limit, and search settings. Both evaluations disable
caching. The source hashes and a comparison of the Python code confirm that the
caption prompt is the only behavioral change between the two runs.

### Run Log — After

Executed from the project directory after the single prompt change:

```bash
.venv/bin/python -u run_eval.py --label after
```

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. Matching query completes all three tools | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. Impossible query stops before the second tool | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. Selected item reaches the outfit tool unchanged in identity | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. Fit card includes full title, price, and platform once each | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. Known-match searches return nonempty results within the price ceiling | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

**Before and after, compared against the original targets**

| Criterion | Target | Before | After |
|---|---|---|---|
| 1. Matching query completes all three tools | 4 of 5 | MET (5/5) | MET (5/5) |
| 2. Impossible query stops before the second tool | 5 of 5 | MET (5/5) | MET (5/5) |
| 3. Selected item reaches the outfit tool unchanged in identity | 5 of 5 | MET (5/5) | MET (5/5) |
| 4. Fit card includes full title, price, and platform once each | 4 of 5 | MISSED (0/5) | MET (5/5) |
| 5. Known-match searches return nonempty results within the price ceiling | 5 of 5 | MET (5/5) | MET (5/5) |

- [Before: complete run log](results/run_2026-10-13_224415_before.md)
- [After: complete run log](results/run_2026-10-13_232157_after.md)
- [After: raw sessions, tool-entry arguments, responses, and source hashes](results/run_2026-10-13_232157_after.json)
- After-run usage: **40 uncached model calls**, 30,044 prompt tokens and 6,934 output tokens.
- The extra empty-wardrobe diagnostic completed all five tries with nonempty
  outfit advice and a fit card. It is separate from the five scored criteria.

**Real output from one after-run try per criterion**

The following excerpts come from the saved first try of each scenario. Result
formatting is produced by `run_eval.py::write_report`; each result's source is
named below. The full log and raw evidence preserve all five tries.

**1. Full three-tool run — `agent.py::run_agent` and `tools.py::create_fit_card`**

```text
[1] search_listings (via MCP)
      in:  {description: vintage graphic tee, size: None, max_price: 30.0}
      out: 10 items: Y2K Baby Tee — Butterfly Print, Graphic Tee — 2003 Tour Bootleg Style, Vintage Band Tee — Faded Grey … +7 more
      →    branch: use the first ranked listing for the outfit
[2] suggest_outfit
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), wardrobe: {items: 10 items: {'id': 'w_001', 'name': 'Baggy straight-leg jeans, dark wash…}}
      out: Here is an outfit featuring your selected thrifted item:  ### Outfit: Y2K Streetwear Contrast  **Selected Thri…
[3] create_fit_card
      in:  {new_item: lst_002: Y2K Baby Tee — Butterfly Print ($18.0, depop), outfit: Here is an outfit featuring your selected thrifted item:  ### Outfit: Y2K Streetwear Contrast  **Selected Thri…}
      out: Channeling pure nostalgic streetwear energy by pairing this fitted little top with baggy dark wash denim and m…

Fit card:
Channeling pure nostalgic streetwear energy by pairing this fitted little top with baggy dark wash denim and my favorite chunky sneakers. I just scored this Y2K Baby Tee — Butterfly Print on depop for $18.00 and it instantly unlocked the ultimate early-2000s outfit vibe.
```

**2. Empty-search stop — `agent.py::run_agent`**

```text
[1] search_listings (via MCP)
      in:  {description: designer ballgown, size: XXS, max_price: 5.0}
      out: [] (empty)
      →    branch: empty search, stopping before outfit and caption

No matching listings. Try different keywords, another size, or a higher budget.
```

**3. Actual received item — `run_eval.py::run_once`, intercepting `tools.py::suggest_outfit`**

```text
- selected_item: lst_002 — Y2K Baby Tee — Butterfly Print ($18.0, depop)
search_listings (via MCP); returned successfully
suggest_outfit; received new_item.id=lst_002; returned successfully
create_fit_card; received new_item.id=lst_002; returned successfully
```

**4. Caption details — `tools.py::create_fit_card`**

```text
Channeling all the early-2000s streetwear energy today by styling my Y2K Baby Tee — Butterfly Print with baggy dark wash jeans and a black denim jacket. I scored this fitted little graphic top on depop for just $18.00, and it balances out the loose bottoms so well.
```

This caption contains `Y2K Baby Tee — Butterfly Print`, `$18.00`, and `depop`
exactly once each. Every criterion-4 after-run caption satisfies the same checks;
all five captions are distinct and came from fresh model calls.

**5. Budget searches — `mcp_server.py::search_listings`, delegating to `tools.py::search_listings`**

```text
{'description': 'graphic tee', 'size': None, 'max_price': 30.0}
lst_002: Y2K Baby Tee — Butterfly Print — $18.00
lst_006: Graphic Tee — 2003 Tour Bootleg Style — $24.00
lst_017: Mesh Long-Sleeve Top — Black — $15.00
lst_033: Vintage Band Tee — Faded Grey — $19.00
lst_011: Low-Rise Cargo Pants — Khaki — $27.00
lst_015: Vintage Graphic Hoodie — Faded Black — $26.00

{'description': 'flannel', 'size': None, 'max_price': 30.0}
lst_003: Oversized Flannel Shirt — Plaid Red/Black — $22.00

{'description': 'tank', 'size': None, 'max_price': 30.0}
lst_023: Crochet Halter Top — Cream — $22.00

{'description': 'belt', 'size': None, 'max_price': 30.0}
lst_014: Leather Belt — Brown, Braided — $12.00

{'description': 'vintage', 'size': None, 'max_price': 30.0}
lst_002: Y2K Baby Tee — Butterfly Print — $18.00
lst_003: Oversized Flannel Shirt — Plaid Red/Black — $22.00
lst_006: Graphic Tee — 2003 Tour Bootleg Style — $24.00
lst_012: Oversized Crewneck Sweatshirt — Vintage Navy — $20.00
lst_013: 90s Silk Slip Dress — Floral, Midi Length — $30.00
lst_014: Leather Belt — Brown, Braided — $12.00
lst_015: Vintage Graphic Hoodie — Faded Black — $26.00
lst_016: High-Waisted Denim Shorts — Cutoff — $24.00
lst_020: Henley Long Sleeve — Washed Burgundy — $16.00
lst_021: Straight Leg Khaki Trousers — Olive — $29.00

```

Every search is nonempty and every returned price is within $30.00 in all five
after-run trials, as in the baseline.

**Did it help, and how do I know:** The prompt change helped: criterion 4
improved from 0 of 5 to 5 of 5 passes against its unchanged 4-of-5 target,
and the other four criteria remained at 5 of 5.

The baseline supplied the full title but allowed an item description; every
baseline caption shortened it. After the prompt explicitly required the full
title verbatim, every evaluated caption copied it exactly once while also
including the correct price and platform once. The identical scenarios and
scoring rules, uncached requests, and source hashes support this comparison.
This is evidence from five trials for this selected listing, rather than a
claim that every future caption for every listing will comply.

---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [x] criteria.md has five numbered criteria, each with a target
       [x] Each criterion has a reason underneath it
       [x] All five unit 3 sections above have real content
       [x] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [x] Planning Loop names the branch rule and agent.py::run_agent
       [x] Sample Run: one full query plus the three per-tool tests, as text
       [x] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [x] A verdict on every criterion
       [x] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [x] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
