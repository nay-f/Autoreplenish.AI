"""Unit Tests for the Bedrock Reasoning Engine & Guardrails (PRD Section 11.5, 15.7, 16).

Covers: real invoke_model payload shape, strict JSON parsing guardrails, and the
requirement that the deterministic rule-based engine ONLY engages after a
Bedrock exception and ALWAYS flags is_fallback=True.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from src.services.bedrock_service import BedrockReasoningService, SYSTEM_PROMPT_V1
from conftest import (
    FakeBedrockClient,
    build_context,
    sku_perishable_fragile,
    sku_short_shelf_life,
    sku_non_perishable,
    _valid_bedrock_json,
)


class TestBedrockReasoning(unittest.TestCase):

    def setUp(self):
        self.sku = sku_perishable_fragile()
        self.context = build_context(self.sku)

    # ---------------------------------------------------------
    # Live invocation
    # ---------------------------------------------------------
    def test_invoke_model_is_called_with_correct_payload(self):
        client = FakeBedrockClient()
        service = BedrockReasoningService(bedrock_client=client)

        result = service.generate_recommendation(self.context)

        self.assertIsNotNone(result)
        self.assertFalse(result.is_fallback)
        self.assertEqual(result.recommended_qty, 24)
        self.assertEqual(result.risk_level, "medium")
        self.assertEqual(result.prompt_version, "v1.0")

        self.assertEqual(len(client.invocations), 1)
        invocation = client.invocations[0]
        self.assertEqual(invocation["modelId"], "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.assertEqual(invocation["contentType"], "application/json")
        self.assertEqual(invocation["accept"], "application/json")

        body = invocation["body"]
        self.assertEqual(body["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(body["max_tokens"], 1024)
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(body["system"], SYSTEM_PROMPT_V1)
        self.assertEqual(len(body["messages"]), 1)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn("Telur Ayam Ras Segar 1kg", body["messages"][0]["content"])
        self.assertIn("shelf_life_days", body["messages"][0]["content"])

    def test_client_is_real_boto3_runtime_type(self):
        """The default constructor must build a genuine bedrock-runtime client."""
        service = BedrockReasoningService(bedrock_client=None)
        self.assertEqual(service.client.meta.service_model.service_name, "bedrock-runtime")
        self.assertEqual(service.client.meta.region_name, "ap-southeast-1")

    def test_retries_then_falls_back_on_exception(self):
        from botocore.exceptions import ClientError

        client = FakeBedrockClient(
            raise_exc=ClientError({"Error": {"Code": "ThrottlingException"}}, "InvokeModel")
        )
        service = BedrockReasoningService(bedrock_client=client)

        result = service.generate_recommendation(self.context)

        # 1 initial attempt + MAX_BEDROCK_RETRIES retries
        self.assertEqual(len(client.invocations), 3)
        self.assertTrue(result.is_fallback)
        self.assertIsNotNone(result.reasoning_narrative)
        self.assertGreater(result.recommended_qty, 0)
        # The degraded mode must be disclosed in the output itself.
        self.assertTrue(any("fallback" in w.lower() for w in result.warnings))

    def test_retries_when_schema_validation_fails_then_falls_back(self):
        client = FakeBedrockClient(response_text="This is not JSON at all")
        service = BedrockReasoningService(bedrock_client=client)

        result = service.generate_recommendation(self.context)

        self.assertEqual(len(client.invocations), 3)
        self.assertTrue(result.is_fallback)

    def test_missing_required_keys_triggers_fallback(self):
        client = FakeBedrockClient(response_text=json.dumps({"recommended_qty": 10}))
        service = BedrockReasoningService(bedrock_client=client)
        result = service.generate_recommendation(self.context)
        self.assertTrue(result.is_fallback)

    def test_successful_second_attempt_stops_retrying(self):
        """A valid response on attempt 2 must short-circuit further retries."""
        garbage = FakeBedrockClient(response_text="not-json")
        valid = FakeBedrockClient(response_text=_valid_bedrock_json())
        candidates = [garbage, valid]

        client = FakeBedrockClient()

        def flaky_invoke(*args, **kwargs):
            delegate = candidates.pop(0) if candidates else valid
            return delegate.invoke_model(*args, **kwargs)

        client.invoke_model = flaky_invoke
        service = BedrockReasoningService(bedrock_client=client)

        result = service.generate_recommendation(self.context)

        self.assertFalse(result.is_fallback)
        self.assertEqual(result.recommended_qty, 24)
        self.assertEqual(len(garbage.invocations), 1)
        self.assertEqual(len(valid.invocations), 1)

    # ---------------------------------------------------------
    # Strict JSON parsing guardrails
    # ---------------------------------------------------------
    def test_json_validation_strict_parsing(self):
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        parsed = service._parse_and_validate_json(_valid_bedrock_json())
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.recommended_qty, 24)
        self.assertAlmostEqual(parsed.confidence_score, 0.91, places=5)
        self.assertIn("below_threshold", parsed.key_factors)
        self.assertFalse(parsed.is_fallback)

    def test_markdown_fences_are_stripped(self):
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        fenced = f"```json\n{_valid_bedrock_json()}\n```"
        parsed = service._parse_and_validate_json(fenced)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.recommended_qty, 24)

    def test_invalid_json_returns_none(self):
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        self.assertIsNone(service._parse_and_validate_json("NOT_A_VALID_JSON_STRING"))

    def test_confidence_score_is_clamped(self):
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        data = json.loads(_valid_bedrock_json())
        data["confidence_score"] = 7.5
        parsed = service._parse_and_validate_json(json.dumps(data))
        self.assertLessEqual(parsed.confidence_score, 1.0)

    # ---------------------------------------------------------
    # Rule-based fallback quality
    # ---------------------------------------------------------
    def test_fallback_is_more_conservative_than_normal(self):
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        rec = service._rule_based_fallback(self.context)
        self.assertTrue(rec.is_fallback)
        self.assertLess(rec.recommended_qty, rec.normal_qty)
        self.assertIn("below_threshold", rec.key_factors)
        self.assertIn("fragile", " ".join(rec.key_factors))

    def test_short_shelf_life_caps_quantity(self):
        """A 3-day shelf life SKU must never be ordered beyond its sellable window."""
        ctx = build_context(sku_short_shelf_life())
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        rec = service._rule_based_fallback(ctx)
        self.assertTrue(rec.is_fallback)
        # burn_rate 8/day * 3 day shelf life = 24 max sellable
        self.assertLessEqual(rec.recommended_qty, 24)
        self.assertTrue(
            any("shelf_life" in k for k in rec.key_factors)
            or any("kedaluwarsa" in w.lower() for w in rec.warnings)
        )

    def test_non_perishable_is_not_capped(self):
        ctx = build_context(sku_non_perishable())
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        rec = service._rule_based_fallback(ctx)
        self.assertTrue(rec.is_fallback)
        self.assertNotIn("short_shelf_life_365d", rec.key_factors)

    def test_cold_start_lowers_confidence_and_raises_risk(self):
        ctx = build_context(sku_perishable_fragile())
        ctx.sku.is_cold_start = True
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        rec = service._rule_based_fallback(ctx)
        self.assertEqual(rec.risk_level, "high")
        self.assertLess(rec.confidence_score, 0.7)
        self.assertIn("cold_start", " ".join(rec.key_factors))

    def test_narrative_is_indonesian(self):
        ctx = build_context(sku_perishable_fragile())
        service = BedrockReasoningService(bedrock_client=FakeBedrockClient())
        rec = service._rule_based_fallback(ctx)
        self.assertRegex(rec.reasoning_narrative.lower(), r"stok|kuota|threshold|rekomendasi")


if __name__ == "__main__":
    unittest.main()
