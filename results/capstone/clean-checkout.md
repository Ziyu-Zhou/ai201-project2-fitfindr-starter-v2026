# Clean-checkout verification

Verified November 17, 2026 at 10:18 PM PST. A new local clone of this same repository was created
with `git clone --no-hardlinks`, at commit `2e140bdcaac5b0851f4a01ca8a0fed1e08d9d9ed`. No existing virtual
environment, model cache, or untracked source files were copied into the clone.
This commit contains the final production implementation; later commits add
evaluation evidence and documentation.

## Setup

Created a fresh environment with CPython 3.13.11 and installed
`requirements-capstone.txt` from the package index. The installed `pip freeze`
output matched every pin exactly. `pip check` reported:

```text
No broken requirements found.
```

Setup requires network access to install the packages. The first restricted
attempt could not access packages; installation succeeded with network access.
There are no local model files to download. Listings and wardrobe data were
present in the clean checkout.

## Development verification

Executed the documented unittest discovery command in the new environment.
All **19 tests passed**. They exercise real local MCP calls where applicable,
with provider calls controlled; no live model responses are claimed by these
development checks. Complete output: [clean-checkout-tests.txt](clean-checkout-tests.txt).

## Real missing-configuration failure

Executed the single documented request command without GEMINI_API_KEY:

```bash
.venv/bin/python app.py ask 'graphic tee under $30, size M'
```

It exited normally, retained the selected listing, and returned an outfit-stage
model error. No response was injected or fabricated. Complete output:
[clean-checkout-missing-key.txt](clean-checkout-missing-key.txt). The persistent
record is [clean-checkout-missing-key.jsonl](clean-checkout-missing-key.jsonl).

## Live start-command verification

Ran the same documented command with a configured API key and caching off.
The API key was supplied privately through the process environment; it was not
written into the clone or committed. The real MCP search, outfit generation,
and caption generation all completed, and exactly one JSONL record persisted.
The record reports 2 model calls and
1740 prompt + 375
output = 2115 reported tokens.

Complete printed output: [clean-checkout-live.txt](clean-checkout-live.txt).
Persistent record: [clean-checkout-live.jsonl](clean-checkout-live.jsonl).
This extra reproducibility run is separate from the three-trial evaluations and
the ten-run cost sample.
