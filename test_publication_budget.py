"""Offline budget contract tests; provider generation is never invoked."""
from copy import deepcopy
from datetime import datetime, timedelta
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import publication_budget as budget

NOW = datetime(2026, 11, 9, 20, tzinfo=budget.TIMEZONE)


def body():
    return {"model": budget.MODEL, "instructions": "Translate faithfully.",
            "input": [{"role": "user", "content": "Ἀθῆναι"}],
            "tools": [{"type": "function", "name": "submit_translation", "parameters": {"type": "object"}}],
            "tool_choice": {"type": "function", "name": "submit_translation"},
            "reasoning": {"effort": "medium"}}


def client(tokens=3413):
    return SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(
        input_tokens=SimpleNamespace(count=Mock(return_value=SimpleNamespace(input_tokens=tokens)))))


class BudgetTests(unittest.TestCase):
    def test_exact_count_includes_tool_schema_and_rounds_up(self):
        provider = client()
        request, quote = budget.quote_request(provider, body(), now=NOW)
        self.assertEqual(quote["reserved_micro_usd"], 14507)
        self.assertEqual(request["max_output_tokens"], 2048)
        self.assertEqual(request["prompt_cache_options"], {"mode": "implicit", "ttl": "30m"})
        self.assertEqual(provider.responses.input_tokens.count.call_args.kwargs["tools"], body()["tools"])
        self.assertNotIn("max_output_tokens", provider.responses.input_tokens.count.call_args.kwargs)
        self.assertLessEqual(50 * quote["reserved_micro_usd"], budget.DAILY_MICRO_USD)
        self.assertEqual(budget.DAILY_MICRO_USD, 1000000)
        self.assertEqual(budget.MONTHLY_MICRO_USD, 30000000)

    def test_count_failure_unknown_model_endpoint_tier_and_context_fail_closed(self):
        provider = client()
        provider.responses.input_tokens.count.side_effect = RuntimeError("unavailable")
        with self.assertRaises(budget.BudgetBlocked):
            budget.quote_request(provider, body(), now=NOW)
        for changed in ({"model": "gpt-6-astra"}, {"service_tier": "priority"},
                        {"prompt_cache_options": {"mode": "implicit", "ttl": "12h"}},
                        {"max_output_tokens": 4096}, {"truncation": "auto"}):
            with self.subTest(changed=changed), self.assertRaises(budget.BudgetBlocked):
                budget.quote_request(client(), {**body(), **changed}, now=NOW)
        for tokens in (None, -1, True, 0, 32769):
            with self.subTest(tokens=tokens), self.assertRaises(budget.BudgetBlocked):
                budget.quote_request(client(tokens), body(), now=NOW)
        provider = client()
        provider.base_url = "https://regional.api.openai.com/v1"
        with self.assertRaises(budget.BudgetBlocked):
            budget.quote_request(provider, body(), now=NOW)
        provider.responses.input_tokens.count.assert_not_called()

    def test_pricing_expiry_includes_entire_batch_window(self):
        with self.assertRaises(budget.BudgetBlocked):
            budget.quote_request(client(), body(), now=budget.PRICE_EXPIRES - timedelta(hours=24))
        budget.check_price(budget.PRICE_EXPIRES - timedelta(hours=25))

    def test_output_cap_cannot_publish_truncated_function(self):
        partial = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                   "output": [{"type": "function_call", "name": "submit_translation",
                               "arguments": json.dumps({"translation": "Truncated but valid JSON"})}]}
        with self.assertRaises(budget.BudgetBlocked):
            budget.require_complete_response(partial)
        partial["status"] = "completed"
        with self.assertRaises(budget.BudgetBlocked):
            budget.require_complete_response(partial)
        budget.require_complete_response({"status": "completed", "output": []})

    def test_reservations_carry_through_terminal_collection_day_and_month(self):
        admitted = datetime(2026, 10, 31, 23, tzinfo=budget.TIMEZONE)
        closed = datetime(2026, 11, 1, 1, tzinfo=budget.TIMEZONE)
        entry = {"reserved_at": admitted.isoformat(), "closed_at": closed.isoformat(), "reserved_micro_usd": 900000}
        november = datetime(2026, 11, 1, 22, tzinfo=budget.TIMEZONE)
        self.assertEqual(budget.period_totals([entry], november), (900000, 900000))
        self.assertEqual(budget.period_totals([entry], november + timedelta(days=1)), (0, 900000))
        entry["closed_at"] = None  # unknown submission must carry indefinitely
        self.assertEqual(budget.period_totals([entry], NOW), (900000, 900000))
        december = datetime(2026, 12, 1, tzinfo=budget.TIMEZONE)
        self.assertEqual(budget.period_totals([entry], december), (900000, 900000))

    def test_failure_does_not_refund_reservation_and_retries_add(self):
        entries = [{"reserved_at": NOW.isoformat(), "closed_at": NOW.isoformat(), "reserved_micro_usd": 500001},
                   {"reserved_at": NOW.isoformat(), "closed_at": None, "reserved_micro_usd": 500000}]
        self.assertEqual(budget.period_totals(entries, NOW), (1000001, 1000001))

    def test_legacy_bootstrap_is_upper_bound_including_cache_writes(self):
        metadata = {"api_mode": "responses", "request_payload": {"body": body()}}
        item = budget.legacy_reservation({"usage": {"input_tokens": 3413, "output_tokens": 186}}, metadata, NOW, NOW)
        self.assertEqual(item["reserved_micro_usd"], 9463)
        with self.assertRaises(budget.BudgetBlocked):
            budget.legacy_reservation({"usage": {"input_tokens": 607213, "output_tokens": 32811}}, metadata, NOW, NOW)

    def test_legacy_missing_usage_fails_closed(self):
        with self.assertRaises(budget.BudgetBlocked):
            budget.legacy_reservation({}, {"api_mode": "responses", "request_payload": {"body": body()}}, NOW, NOW)

    def test_scope_excludes_human_experiments_and_repeats(self):
        self.assertTrue(budget.is_normal_publication("gpt-5.5", budget.MODEL, 1, "enqueue_translation_runs.py"))
        self.assertFalse(budget.is_normal_publication("gpt-5.5", budget.MODEL, 1, "human-eval:test"))
        self.assertFalse(budget.is_normal_publication("gpt-5.5", budget.MODEL, 2, ""))
        self.assertFalse(budget.is_normal_publication("gpt-5.5_v4_reasoning", budget.MODEL, 1, ""))

    def test_provider_response_breach_detected(self):
        _, quote = budget.quote_request(client(), body(), now=NOW)
        self.assertFalse(budget.response_breaches_quote({"usage": {"input_tokens": 3413, "output_tokens": 2048}}, quote))
        self.assertTrue(budget.response_breaches_quote({"usage": {"input_tokens": 3414, "output_tokens": 20}}, quote))
        self.assertTrue(budget.response_breaches_quote({"service_tier": "priority"}, quote))
        self.assertTrue(budget.response_breaches_quote({"prompt_cache_options": {"mode":"implicit","ttl":"12h"}}, quote))
        self.assertTrue(budget.response_breaches_quote({"usage":{"input_tokens_details":{"cache_write_tokens_details":{"ttl_12h_tokens":1}}}}, quote))
        self.assertFalse(budget.response_breaches_quote({"prompt_cache_retention":"24h", "usage":{"input_tokens_details":{"cache_write_tokens_details":{"ttl_12h_tokens":0}}}}, quote))


if __name__ == "__main__":
    unittest.main()
