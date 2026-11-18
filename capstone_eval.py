#!/usr/bin/env python3
"""Evaluate the selected capstone criteria; preserve every real response.

Controlled cases inject provider responses/errors through tools.generate only.
Search always goes through the real MCP subprocess. Live cases never replace
the provider. This script refuses to overwrite an existing evidence directory.
"""

import argparse
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import statistics
import subprocess
import sys
from unittest.mock import patch

import agent
import config
import generate
import tools
from utils.data_loader import get_example_wardrobe

QUERY = "graphic tee under $30, size M"
OUTFIT = "Controlled fixture outfit: pair the selected tee with black jeans and white sneakers."
CAPTION = "Controlled fixture caption; this is not a live model response."
FAILURES = (
    ("unavailable", generate.ModelUnavailable, "The model is unavailable."),
    ("timeout", TimeoutError, "The model request timed out."),
    ("quota", generate.QuotaGuard, "The model request quota is exhausted."),
    ("authentication", generate.ModelUnavailable, "Check the model API key configuration."),
    ("rate_limit", generate.ModelUnavailable, "Provider rate-limit retries are exhausted."),
)
BLANKS = ("", " ", "\n", "\t", " \n ")


def read_records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def attempt(kind, log_path, *, failure=None, blank=None):
    """Capture a direct caller's actual result, tool entries, trace, and log."""
    provider_calls = []
    search_results = []
    query = ("tee under $-5" if kind == "invalid" else
             "designer ballgown size XXS under $5" if kind == "no_match" else QUERY)
    wardrobe = get_example_wardrobe()
    before = len(read_records(log_path))
    original_search = agent.mcp_client.call_tool

    def search(name, arguments):
        result = original_search(name, arguments)
        search_results.append(result)
        return result

    def provider(*args, **kwargs):
        index = len(provider_calls)
        provider_calls.append({"prompt": args[0]})
        stage = "outfit" if index == 0 else "caption"
        if kind == f"{stage}_failure":
            _, error_type, message = failure
            raise error_type(message)
        if kind == f"{stage}_blank":
            return blank
        return OUTFIT if stage == "outfit" else CAPTION

    record = {
        "kind": kind, "mode": "live" if kind == "live" else "controlled",
        "input": {"query": query, "wardrobe": wardrobe},
        "fault": failure[0] if failure else None,
        "blank": blank, "session": None, "exception": None,
    }
    with ExitStack() as stack:
        stack.enter_context(patch.object(config, "RUN_LOG_PATH", log_path))
        stack.enter_context(patch.object(agent.mcp_client, "call_tool", search))
        caption = stack.enter_context(patch.object(agent, "create_fit_card", wraps=agent.create_fit_card))
        if kind != "live":
            stack.enter_context(patch.object(tools, "generate", provider))
        printed = stack.enter_context(redirect_stdout(StringIO()))
        try:
            record["session"] = agent.run_agent(query, wardrobe, trace_enabled=True)
        except Exception as error:
            record["exception"] = f"{type(error).__name__}: {error}"
        record["caption_calls"] = caption.call_count
        record["trace"] = printed.getvalue()
    record["controlled_provider_calls"] = provider_calls
    record["search_results"] = search_results
    record["log_entries"] = read_records(log_path)[before:]
    return record


def preserved(record):
    session = record["session"]
    return (record["exception"] is None and session is not None
            and bool(record["search_results"]) and bool(record["search_results"][0])
            and session["selected_item"] == record["search_results"][0][0])


def failed_safely(record, stage):
    session = record["session"]
    if not preserved(record) or not session.get("error"):
        return False
    if session.get("error_stage") != stage or stage not in session["error"].lower():
        return False
    if session["fit_card"] is not None:
        return False
    if stage == "outfit":
        return session["outfit_suggestion"] is None and record["caption_calls"] == 0
    return session["outfit_suggestion"] == OUTFIT


def logging_passes(record):
    session = record["session"]
    if session is None or record["exception"] or len(record["log_entries"]) != 1:
        return False
    entry = record["log_entries"][0]
    try:
        datetime.fromisoformat(entry["timestamp"])
        expected = {"success": "completed", "invalid": "rejected", "no_match": "no_matches"}.get(
            record["kind"], "failed")
        return (entry["run_id"] == session["run_id"]
                and entry["input"] == record["input"]
                and entry["status"] == expected
                and isinstance(entry["duration_ms"], (float, int))
                and entry["duration_ms"] >= 0
                and all(entry["output"][key] == session[key] for key in entry["output"])
                and all(key in entry["output"] for key in (
                    "selected_item", "outfit_suggestion", "fit_card", "error", "error_stage", "error_code"))
                and (expected != "failed" or entry["output"]["error_stage"] in ("outfit", "caption")))
    except (KeyError, TypeError, ValueError):
        return False


def live_passes(record):
    session = record["session"]
    return bool(preserved(record) and not session["error"]
                and session["outfit_suggestion"] and session["outfit_suggestion"].strip()
                and session["fit_card"] and session["fit_card"].strip()
                and [step["stage"] for step in session["steps"]] == ["search", "outfit", "caption"]
                and not session["usage"]["cache_enabled"])


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def evaluate(criterion, trial, directory):
    log_path = directory / f"criterion-{criterion}-trial-{trial}.jsonl"
    records = []
    if criterion in (1, 2):
        stage = "outfit" if criterion == 1 else "caption"
        records = [attempt(f"{stage}_failure", log_path, failure=error) for error in FAILURES]
        passed = sum(failed_safely(record, stage) for record in records)
        target = 5
    elif criterion == 3:
        for kind in ("success", "invalid", "no_match", "outfit_failure", "caption_failure"):
            records.extend(attempt(kind, log_path, failure=FAILURES[0]) for _ in range(2))
        passed = sum(logging_passes(record) for record in records)
        # Verify persisted content in a different interpreter, after all writes close.
        check = subprocess.run([sys.executable, "-c",
            "import json,sys; print(len([json.loads(s) for s in open(sys.argv[1])]))",
            str(log_path)], capture_output=True, text=True, check=True)
        ids = [r["log_entries"][0]["run_id"] for r in records if len(r["log_entries"]) == 1]
        if check.stdout.strip() != "10" or len(set(ids)) != 10:
            passed = 0
        target = 10
    elif criterion == 4:
        records = [attempt("live", log_path) for _ in range(5)]
        passed = sum(live_passes(record) for record in records)
        target = 4
    else:
        for stage in ("outfit", "caption"):
            records.extend(attempt(f"{stage}_blank", log_path, blank=blank) for blank in BLANKS)
        passed = sum(failed_safely(record, "outfit" if index < 5 else "caption")
                     for index, record in enumerate(records))
        target = 10
    result = {"criterion": criterion, "trial": trial, "passed": passed,
              "total": len(records), "target": target, "met": passed >= target,
              "records": records}
    write_json(directory / f"criterion-{criterion}-trial-{trial}.json", result)
    print(f"Criterion {criterion}, trial {trial}: {passed}/{len(records)}; "
          f"{'MET' if result['met'] else 'MISSED'}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after", "cost"), required=True)
    parser.add_argument("--mode", choices=("controlled", "live", "all", "cost"), default="all")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Evidence directory already exists; choose a new path to preserve prior results.")
    config.CACHE_ENABLED = False
    args.output.mkdir(parents=True)
    metadata = {
        "phase": args.phase, "mode": args.mode,
        "started": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": sys.version, "model": config.MODEL, "cache_enabled": False,
        "source_sha256": {name: hashlib.sha256((config.ROOT / name).read_bytes()).hexdigest()
                          for name in ("criteria.md", "agent.py", "tools.py", "generate.py",
                                       "run_log.py", "capstone_eval.py", "requirements-capstone.txt")},
        "evidence_note": "Controlled provider fixtures/faults are labeled; all searches use real MCP.",
    }
    write_json(args.output / "metadata.json", metadata)
    if args.mode == "cost":
        records = [attempt("live", args.output / "cost.jsonl") for _ in range(10)]
        sessions = [r["session"] for r in records if r["session"] is not None]
        completed = sum(live_passes(r) for r in records)
        report = {"attempts": 10, "completed": completed, "records": records}
        if len(sessions) == 10:
            report.update(
                mean_duration_ms=statistics.mean(s["duration_ms"] for s in sessions),
                mean_prompt_tokens=statistics.mean(s["usage"]["tokens"]["prompt"] for s in sessions),
                mean_output_tokens=statistics.mean(s["usage"]["tokens"]["output"] for s in sessions),
                mean_total_tokens=statistics.mean(s["usage"]["tokens"]["total"] for s in sessions),
                total_model_calls=sum(s["usage"]["model_calls"] for s in sessions),
            )
        write_json(args.output / "summary.json", report)
        print(f"Measured ten uncached live attempts; {completed}/10 completed.", flush=True)
        return
    criteria = ([1, 2, 3, 5] if args.mode == "controlled" else
                [4] if args.mode == "live" else [1, 2, 3, 4, 5])
    results = [evaluate(criterion, trial, args.output)
               for criterion in criteria for trial in range(1, 4)]
    rows = []
    for criterion in criteria:
        trials = [r for r in results if r["criterion"] == criterion]
        rows.append({"criterion": criterion, "target": f"{trials[0]['target']}/{trials[0]['total']}",
                     "trials": [f"{r['passed']}/{r['total']}" for r in trials],
                     "verdict": "MET" if all(r["met"] for r in trials) else "MISSED"})
    write_json(args.output / "summary.json", {"metadata": metadata, "rows": rows})
    markdown = "| Criterion | Target | Trial 1 | Trial 2 | Trial 3 | Verdict |\n|---|---|---|---|---|---|\n"
    for row in rows:
        markdown += f"| {row['criterion']} | {row['target']} | " + " | ".join(row["trials"]) + f" | {row['verdict']} |\n"
    (args.output / "summary.md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
