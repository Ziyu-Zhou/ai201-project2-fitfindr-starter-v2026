# FitFindr capstone acceptance criteria

Chosen before capstone evaluation results were collected. The student selected
examples 1, 2, 4, 5, and 6 supplied by Codex. The wording below makes their trial
procedure explicit; the numerical targets and reasons are the selected examples.
These are AI-assisted criteria, not a claim of unaided student authorship.
The original Units 3–4 criteria are preserved in criteria-unit3-4.md.

Run each criterion in three separate trials, with no code or target changes
between trials. A criterion is MET only when every trial reaches its target.
Use the same scenarios before and after the improvement. Deliberate provider
failures and fixture successes must be labeled as controlled, not live outputs.

## 1. An outfit failure preserves the selected listing

For each trial, trigger five model failures during outfit generation. In all
5 of 5 attempts, run_agent returns a session rather than raising, preserves
the selected listing returned by search, supplies a nonempty error naming the
outfit stage, leaves outfit_suggestion and fit_card as None, and never calls
the caption tool. Exercise unavailability, timeout, and quota-exhaustion errors.

Why this target: finding the item succeeded, so a later failure should preserve
it. Returning state and skipping the next stage are deterministic decisions;
allowing even one failure would permit loss of completed work.

## 2. A caption failure preserves the completed outfit

For each trial, trigger five model failures during caption generation after a
controlled successful outfit response. In all 5 of 5 attempts, run_agent
returns a session rather than raising, preserves the selected listing and the
exact completed outfit, sets fit_card to None, and supplies a nonempty error
naming the caption stage. Exercise the same failure types as criterion 1.

Why this target: the selected item and outfit remain useful to the user. Their
preservation is controlled by Python state handling, so 5 of 5 is appropriate.

## 3. Every request is recorded in the structured log

For each trial, execute ten agent requests: two controlled successes, two
invalid-budget requests, two no-match searches, two outfit failures, and two
caption failures. Read the persistent JSONL log, not the printed trace. All
10 of 10 requests must each have exactly one distinct run record containing a
parseable timestamp, run ID, input, output, status, and a nonnegative numeric
duration_ms. Logged input/output must match the actual request/session; status
must distinguish success from rejected input, no matches, and failure. Failed
model requests must identify the failed stage. The log must remain readable
from a second process after the requests finish.

Why this target: missing failures would make diagnosis unreliable. Every request
must be accounted for, including requests that never reach a model.

## 4. The normal workflow still completes

For each trial, run the matching query `graphic tee under $30, size M` five
times with the example wardrobe and caching disabled. Use the real MCP search
and live model, with no replacement responses. At least 4 of 5 requests must
complete search, outfit, and caption generation, returning a selected listing,
nonempty outfit and caption, and no session error or uncaught exception.
Save the actual responses and model usage. A failed provider request counts as
a failure; a controlled fixture cannot substitute for a live attempt.

Why this target: this allows one external-service failure while checking that
the extension preserves normal behavior.

## 5. Empty model responses stop the workflow without losing completed work

For each trial, return each of five deliberately blank provider responses
(`""`, a space, a newline, a tab, and a space/newline combination) at each model
stage through tools.generate. Use the real tool functions and real MCP search.
For outfit generation, all 5 of 5 attempts must return an error, keep the
selected listing, leave the outfit and caption as None, and skip the caption
model call. For caption generation, all 5 of 5 attempts must return an error,
keep the selected listing and exact completed controlled outfit, and leave the
caption as None. An apology string presented as a completed outfit or caption
fails. No attempt may raise to the caller.

Why this target: an empty response should not appear to be successful
generation. Detecting blank text and preserving earlier state are deterministic,
so every blank-response case must be handled.
