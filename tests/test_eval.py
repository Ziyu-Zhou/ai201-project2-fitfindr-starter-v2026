"""Check evaluation evidence without contacting a model or replacing its outputs in live runs."""

from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import agent
from generate import ModelUnavailable
import mcp_client
import run_eval
import scenarios
from utils.data_loader import load_listings


class EvaluationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.item = load_listings()[1]
        self.scenario = scenarios.SCENARIOS[0]

    def test_records_actual_tool_arguments_and_trace_without_changing_results(self):
        with patch.object(mcp_client, "call_tool", return_value=[self.item]) as search, \
                patch.object(agent, "suggest_outfit", return_value="An outfit.") as outfit, \
                patch.object(agent, "create_fit_card", return_value="A caption."), \
                redirect_stdout(StringIO()):
            record = run_eval.run_once(self.scenario)
            # Instrumentation restores the original callable after the run.
            self.assertIs(agent.suggest_outfit, outfit)
            self.assertIs(mcp_client.call_tool, search)

        self.assertIsNone(record["crashed"])
        self.assertEqual(record["session"]["fit_card"], "A caption.")
        self.assertEqual(record["tool_calls"][1]["inputs"]["new_item"]["id"], self.item["id"])
        self.assertIn("[1] search_listings (via MCP)", record["trace"])
        self.assertIn("[3] create_fit_card", record["trace"])
        self.assertEqual(record["model_calls"], 0)

    def test_model_failure_keeps_partial_session_and_received_argument(self):
        with patch.object(mcp_client, "call_tool", return_value=[self.item]), \
                patch.object(agent, "suggest_outfit", side_effect=ModelUnavailable("Unavailable.")), \
                patch.object(agent, "create_fit_card") as caption, \
                redirect_stdout(StringIO()):
            record = run_eval.run_once(self.scenario)

        self.assertEqual(record["crashed"], "ModelUnavailable: Unavailable.")
        self.assertEqual(record["session"]["selected_item"]["id"], self.item["id"])
        self.assertEqual(record["tool_calls"][1]["inputs"]["new_item"]["id"], self.item["id"])
        self.assertIn("error", record["tool_calls"][1])
        self.assertIn("[1] search_listings", record["trace"])
        caption.assert_not_called()

    def test_budget_batch_calls_mcp_for_each_description_without_model_tools(self):
        scenario = next(s for s in scenarios.SCENARIOS if s.get("kind") == "search_batch")
        with patch.object(mcp_client, "call_tool", return_value=[self.item]) as search, \
                patch.object(agent, "suggest_outfit") as outfit, \
                patch.object(agent, "create_fit_card") as caption, \
                redirect_stdout(StringIO()):
            record = run_eval.run_once(scenario)

        self.assertIsNone(record["crashed"])
        self.assertEqual(len(record["search_checks"]), 5)
        self.assertEqual(search.call_count, 5)
        self.assertEqual(
            [call.args[1]["description"] for call in search.call_args_list],
            ["graphic tee", "flannel", "tank", "belt", "vintage"],
        )
        for call in search.call_args_list:
            self.assertEqual(call.args[1]["max_price"], 30.0)
            self.assertIsNone(call.args[1]["size"])
        self.assertIn("[5] search_listings (via MCP)", record["trace"])
        outfit.assert_not_called()
        caption.assert_not_called()


if __name__ == "__main__":
    unittest.main()
