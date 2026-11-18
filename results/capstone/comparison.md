# FitFindr capstone comparison

Criteria were selected and committed in dab804e, before any capstone evaluation
results. First results were committed in cb7054c; the one measured improvement
is 2e140bd. AI supplied the examples and the student selected the five targets.

Three trials per criterion in each phase. Controlled criteria use real MCP
search with injected provider faults/fixtures. Criterion 4 uses live uncached
model requests. Criterion 5 aggregates five blank outputs per stage (10 cases).

## Before the improvement

| Criterion | Target | Trial 1 | Trial 2 | Trial 3 | Verdict |
|---|---|---|---|---|---|
| 1. Outfit failure preserves listing | 5/5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Caption failure preserves outfit | 5/5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Every request is logged | 10/10 | 10/10 | 10/10 | 10/10 | MET |
| 4. Normal live workflow | 4/5 | 5/5 | 5/5 | 5/5 | MET |
| 5. Blank responses stop safely | 10/10 | 0/10 | 0/10 | 0/10 | MISSED |

## After the improvement

| Criterion | Target | Trial 1 | Trial 2 | Trial 3 | Verdict |
|---|---|---|---|---|---|
| 1. Outfit failure preserves listing | 5/5 | 5/5 | 5/5 | 5/5 | MET |
| 2. Caption failure preserves outfit | 5/5 | 5/5 | 5/5 | 5/5 | MET |
| 3. Every request is logged | 10/10 | 10/10 | 10/10 | 10/10 | MET |
| 4. Normal live workflow | 4/5 | 5/5 | 5/5 | 5/5 | MET |
| 5. Blank responses stop safely | 10/10 | 10/10 | 10/10 | 10/10 | MET |

## Diagnosis and change

Criterion 5 missed because tools.py::suggest_outfit and create_fit_card replaced
blank provider text with apology strings. Those nonempty strings flowed through
the normal success branch; a missing outfit even triggered caption generation.
The improvement raises EmptyModelResponse from the affected tool. Existing
agent recovery then preserves completed state, records the failed tool, and
stops. No criterion or target was lowered. Blank cases improved from 0/10 in
each trial to 10/10; all other criteria retained their MET verdicts.

## Measured cost

Ten uncached live agent requests were executed with the real MCP search and
configured model; **10/10 completed**. The measured averages were
**1,752.5 prompt tokens + 370.4 output tokens = 2,122.9
reported prompt/output tokens per request**, using 20 actual
model calls across the ten requests. Mean elapsed agent time was **9.165
seconds**, including any adapter pacing and provider waits.

Method: `generate.token_counts()` and `generate.call_count()` are read before and
after each request in `agent.py::run_agent`; the evaluator averages those deltas.
`time.perf_counter()` measures elapsed time. These token counts came from response
usage metadata, with caching disabled, rather than a pricing page. The sum covers
reported prompt/output tokens; it is not a claim about dollar billing or any
unreported token category. Controlled fault/fixture runs are excluded.

For **100 people making one request each per day**:
`100 × 2,122.9 = 212,290` reported tokens/day
(`175,250` prompt + `37,040` output).
The corresponding measured elapsed-time sum is
`100 × 9.165 = 916.500` seconds/day;
this is an operational projection, not CPU time or a throughput guarantee.
Raw outputs, usage, and timings are in [the cost evidence](cost/summary.json).
