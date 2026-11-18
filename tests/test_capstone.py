"""Development checks for partial state and persistent evidence; no API calls."""

from contextlib import ExitStack, redirect_stdout
from datetime import datetime
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import agent
import app
import config
import generate
import serve
from utils.data_loader import get_example_wardrobe, load_listings


class FailureHandlingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(TemporaryDirectory()))
        self.log = self.directory / "nested" / "runs.jsonl"
        self.stack.enter_context(patch.object(config, "RUN_LOG_PATH", self.log))
        self.item = load_listings()[1]
        self.wardrobe = get_example_wardrobe()
        self.stack.enter_context(patch.object(agent.mcp_client, "call_tool", return_value=[self.item]))

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_outfit_failures_preserve_item_and_skip_caption(self):
        for error in (generate.ModelUnavailable("Offline."), TimeoutError("Timed out."),
                      generate.QuotaGuard("Quota exhausted.")):
            with self.subTest(error=type(error).__name__), \
                    patch.object(agent, "suggest_outfit", side_effect=error), \
                    patch.object(agent, "create_fit_card") as caption:
                session = agent.run_agent("graphic tee", self.wardrobe)
                self.assertEqual(session["selected_item"], self.item)
                self.assertIsNone(session["outfit_suggestion"])
                self.assertIsNone(session["fit_card"])
                self.assertEqual(session["error_stage"], "outfit")
                self.assertIn("Try again", session["error"])
                caption.assert_not_called()
        self.assertEqual(len(self.records()), 3)

    def test_caption_failures_preserve_exact_outfit_and_record_failed_step(self):
        with patch.object(agent, "suggest_outfit", return_value="Keep this exact outfit."), \
                patch.object(agent, "create_fit_card", side_effect=generate.ModelUnavailable("Offline.")), \
                redirect_stdout(StringIO()):
            session = agent.run_agent("graphic tee", self.wardrobe, trace_enabled=True)
        self.assertEqual(session["selected_item"], self.item)
        self.assertEqual(session["outfit_suggestion"], "Keep this exact outfit.")
        self.assertIsNone(session["fit_card"])
        self.assertEqual(session["error_stage"], "caption")
        self.assertIn("[3] create_fit_card", agent.trace.get_trace())
        self.assertIn("Offline.", agent.trace.get_trace())
        self.assertEqual(self.records()[0]["steps"][-1]["status"], "failed")

    def test_cli_shows_completed_work_and_failure_without_none_placeholders(self):
        with patch.object(agent, "suggest_outfit", return_value="Wear it with jeans."), \
                patch.object(agent, "create_fit_card", side_effect=generate.ModelUnavailable("Offline.")), \
                redirect_stdout(StringIO()) as printed:
            app._ask_one("graphic tee", self.wardrobe, False)
        text = printed.getvalue()
        self.assertIn(self.item["title"], text)
        self.assertIn("Wear it with jeans.", text)
        self.assertIn("Caption generation failed", text)
        self.assertNotIn("Fit card:", text)

    def test_http_call_returns_partial_session_instead_of_500(self):
        with patch.object(agent, "suggest_outfit", side_effect=generate.ModelUnavailable("Offline.")):
            response = serve.app.test_client().post("/ask", json={"query": "graphic tee"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["error_stage"], "outfit")
        self.assertEqual(response.json["selected_item"], self.item)

    def test_unexpected_programming_error_is_logged_and_still_raises(self):
        with patch.object(agent, "suggest_outfit", side_effect=KeyError("programming bug")):
            with self.assertRaises(KeyError):
                agent.run_agent("graphic tee", self.wardrobe)
        record = self.records()[0]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["output"]["error_code"], "unexpected_error")
        self.assertEqual(record["output"]["error_stage"], "outfit")

    def test_log_matches_returned_state_and_survives_another_process(self):
        with patch.object(agent, "suggest_outfit", return_value="An outfit."), \
                patch.object(agent, "create_fit_card", return_value="A caption."):
            success = agent.run_agent("graphic tee", self.wardrobe)
        invalid = agent.run_agent("tee under $-5", self.wardrobe)
        with patch.object(agent.mcp_client, "call_tool", return_value=[]):
            empty = agent.run_agent("designer ballgown", self.wardrobe)
        records = self.records()
        self.assertEqual([r["status"] for r in records], ["completed", "rejected", "no_matches"])
        self.assertEqual(len({r["run_id"] for r in records}), 3)
        for record, session in zip(records, [success, invalid, empty]):
            datetime.fromisoformat(record["timestamp"])
            self.assertEqual(record["input"]["query"], session["query"])
            self.assertEqual(record["input"]["wardrobe"], session["wardrobe"])
            self.assertGreaterEqual(record["duration_ms"], 0)
            for key, value in record["output"].items():
                self.assertEqual(value, session[key])
        result = subprocess.run([sys.executable, "-c",
            "import json,sys; print(len([json.loads(s) for s in open(sys.argv[1])]))",
            str(self.log)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "3")

    def test_usage_is_a_per_run_delta_not_the_session_total(self):
        with patch.object(agent, "suggest_outfit", return_value="An outfit."), \
                patch.object(agent, "create_fit_card", return_value="A caption."), \
                patch.object(generate, "call_count", side_effect=[7, 9]), \
                patch.object(generate, "token_counts", side_effect=[
                    {"prompt": 100, "output": 40, "total": 140},
                    {"prompt": 150, "output": 60, "total": 210}]):
            session = agent.run_agent("graphic tee", self.wardrobe)
        self.assertEqual(session["usage"]["model_calls"], 2)
        self.assertEqual(session["usage"]["tokens"], {"prompt": 50, "output": 20, "total": 70})
        self.assertEqual(self.records()[0]["usage"], session["usage"])

    def test_blank_provider_response_stops_at_either_stage(self):
        blanks = ("", " ", "\n", "\t", " \n ")
        for stage in ("outfit", "caption"):
            for blank in blanks:
                with self.subTest(stage=stage, blank=repr(blank)), \
                        patch("tools.generate", side_effect=(
                            [blank, "Should never be requested."] if stage == "outfit"
                            else ["Keep this exact outfit.", blank])) as provider:
                    session = agent.run_agent("graphic tee", self.wardrobe)
                self.assertEqual(session["selected_item"], self.item)
                self.assertEqual(session["status"], "failed")
                self.assertEqual(session["error_stage"], stage)
                self.assertEqual(session["error_code"], "empty_model_response")
                self.assertIsNone(session["fit_card"])
                if stage == "outfit":
                    self.assertIsNone(session["outfit_suggestion"])
                    self.assertEqual(provider.call_count, 1)
                else:
                    self.assertEqual(session["outfit_suggestion"], "Keep this exact outfit.")
                    self.assertEqual(provider.call_count, 2)

    def test_exhausted_provider_rate_limit_uses_the_expected_failure_type(self):
        class UnavailableClient:
            @property
            def models(self):
                return self

            def generate_content(self, **kwargs):
                raise RuntimeError("429 rate limit")

        with patch.object(generate, "_get_client", return_value=UnavailableClient()), \
                patch.object(generate, "_wait_for_slot"), \
                patch.object(generate.time, "sleep"), \
                patch.object(config, "MAX_RETRIES", 1):
            with self.assertRaises(generate.ModelUnavailable):
                generate.generate("development test", cache=False)


if __name__ == "__main__":
    unittest.main()
