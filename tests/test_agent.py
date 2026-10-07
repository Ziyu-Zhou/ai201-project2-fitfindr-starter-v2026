"""Check query constraints and the agent's decisions without making API calls."""

import unittest
from unittest.mock import Mock, patch

import agent
import config
from utils.data_loader import get_example_wardrobe, load_listings


class QueryParsingTests(unittest.TestCase):
    def test_extracts_filters_without_leaving_them_in_search_text(self):
        cases = [
            ("graphic tee under $30, size M", "graphic tee", "M", 30.0),
            ("looking for a vintage graphic tee under $30", "vintage graphic tee", None, 30.0),
            ("90s track jacket in size M", "90s track jacket", "M", None),
            ("tee size s / m under 30.50", "tee", "S/M", 30.5),
            ("jeans size W30 L30", "jeans", "W30 L30", None),
            ("belt size W30", "belt", "W30", None),
            ("sneakers size US 8.5", "sneakers", "US 8.5", None),
            ("sneakers size 8", "sneakers", "8", None),
            ("hat size One Size", "hat", "ONE SIZE", None),
            ("tee size XXS under $0", "tee", "XXS", 0.0),
            ("Find me a denim jacket", "denim jacket", None, None),
            ("under $30; graphic tee; size M", "graphic tee", "M", 30.0),
        ]
        for query, description, size, price in cases:
            with self.subTest(query=query):
                self.assertEqual(agent._parse_query(query), {
                    "description": description, "size": size, "max_price": price,
                })

    def test_rejects_invalid_or_ambiguous_filters(self):
        queries = [
            "tee under $-5", "tee under $abc", "tee under", "tee under $30abc",
            "tee under $30.5.2", "tee under $NaN", "tee under $30 under $40", "tee under $30,000",
            "tee size", "tee size unknown", "tee size -8", "tee size M size L",
            "tee size M/unknown", "tee size M / unknown", "under $30 size M", "", "!!!",
            "tee under $" + "9" * 400,
        ]
        for query in queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                agent._parse_query(query)


class AgentFlowTests(unittest.TestCase):
    def setUp(self):
        self.item = load_listings()[1]
        self.wardrobe = get_example_wardrobe()

    def test_matching_query_runs_tools_in_order_and_preserves_state(self):
        calls = Mock()
        with patch.object(agent, "search_listings", return_value=[self.item]) as search, \
                patch.object(agent, "suggest_outfit", return_value="A styled outfit.") as outfit, \
                patch.object(agent, "create_fit_card", return_value="A fit card.") as caption, \
                patch.object(agent.trace, "check_iterations", wraps=agent.trace.check_iterations) as guard:
            for name, tool in [("search", search), ("outfit", outfit), ("caption", caption)]:
                calls.attach_mock(tool, name)
            session = agent.run_agent("graphic tee under $30, size M", self.wardrobe)

        self.assertEqual([call[0] for call in calls.mock_calls], ["search", "outfit", "caption"])
        search.assert_called_once_with(description="graphic tee", size="M", max_price=30.0)
        self.assertIs(outfit.call_args.args[0], session["selected_item"])
        self.assertIs(outfit.call_args.args[1], session["wardrobe"])
        caption.assert_called_once_with(session["outfit_suggestion"], session["selected_item"])
        self.assertEqual([call.args[0] for call in guard.call_args_list], [1, 2, 3])
        self.assertEqual(session["query"], "graphic tee under $30, size M")
        self.assertEqual(session["search_results"], [self.item])
        self.assertEqual(session["fit_card"], "A fit card.")
        self.assertIsNone(session["error"])

    def test_impossible_query_stops_without_model_calls(self):
        with patch.object(agent, "suggest_outfit") as outfit, \
                patch.object(agent, "create_fit_card") as caption:
            session = agent.run_agent("designer ballgown size XXS under $5", self.wardrobe)

        outfit.assert_not_called()
        caption.assert_not_called()
        self.assertEqual(session["search_results"], [])
        self.assertEqual(session["error"],
                         "No matching listings. Try different keywords, another size, or a higher budget.")
        for field in ["selected_item", "outfit_suggestion", "fit_card"]:
            self.assertIsNone(session[field])

    def test_invalid_filters_stop_before_search(self):
        with patch.object(agent, "search_listings") as search, \
                patch.object(agent, "suggest_outfit") as outfit, \
                patch.object(agent, "create_fit_card") as caption:
            session = agent.run_agent("tee under $-5", self.wardrobe)

        search.assert_not_called()
        outfit.assert_not_called()
        caption.assert_not_called()
        self.assertIn("non-negative", session["error"])
        self.assertEqual(session["parsed"], {})

    def test_iteration_limit_prevents_the_next_tool_from_running(self):
        with patch.object(config, "MAX_ITERATIONS", 1), \
                patch.object(agent, "search_listings", return_value=[self.item]) as search, \
                patch.object(agent, "suggest_outfit") as outfit, \
                patch.object(agent, "create_fit_card") as caption:
            with self.assertRaisesRegex(RuntimeError, "MAX_ITERATIONS"):
                agent.run_agent("graphic tee", self.wardrobe)

        search.assert_called_once()
        outfit.assert_not_called()
        caption.assert_not_called()

    def test_real_tools_complete_with_an_empty_wardrobe_and_mocked_model(self):
        with patch("tools.generate", side_effect=["General styling advice.", "A caption."]) as model:
            session = agent.run_agent("graphic tee under $30, size M", {"items": []})

        self.assertIsNone(session["error"])
        self.assertEqual(session["selected_item"]["id"], self.item["id"])
        self.assertEqual(session["outfit_suggestion"], "General styling advice.")
        self.assertEqual(session["fit_card"], "A caption.")
        self.assertIn("wardrobe is empty", model.call_args_list[0].args[0])
        self.assertIn(session["outfit_suggestion"], model.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
