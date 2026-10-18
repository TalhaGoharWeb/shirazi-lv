"""
Capability registry tests — Stage B.

  1. Registration with namespaced IDs; invalid IDs rejected.
  2. Policy risk overrides tool self-declared risk (never downgradable).
  3. Input schema validation (required fields, types).
  4. Health tracking (success/error/degraded).
  5. Populate from gateway (54 builtins).
  6. by_tool_name deterministic lookup.
"""
import unittest

from core.capabilities import (
    Capability, CapabilityRegistry, get_registry, reset_registry,
    _validate_schema, _normalize_schema,
)


class Registration(unittest.TestCase):
    def setUp(self):
        self.r = CapabilityRegistry()

    def test_valid_id(self):
        c = Capability(id="plugin.my_tool")
        self.assertEqual(self.r.register(c), "plugin.my_tool")

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            self.r.register(Capability(id="not namespaced!"))

    def test_get_and_count(self):
        self.r.register(Capability(id="plugin.a"))
        self.r.register(Capability(id="action.b"))
        self.assertEqual(self.r.count(), 2)
        self.assertIsNotNone(self.r.get("plugin.a"))
        self.assertIsNone(self.r.get("plugin.nope"))


class RiskIntegrity(unittest.TestCase):
    def test_policy_overrides(self):
        r = CapabilityRegistry()
        # 'desktop' is HIGH in policy; a LOW self-declaration must not win.
        r.register(Capability(id="builtin.desktop", risk="LOW"))
        self.assertEqual(r.get("builtin.desktop").risk.upper(), "HIGH")

    def test_unknown_keeps_declared(self):
        r = CapabilityRegistry()
        r.register(Capability(id="plugin.brand_new", risk="MODERATE"))
        # Not in policy — declared risk stands (gateway denies unknowns anyway).
        self.assertEqual(r.get("plugin.brand_new").risk, "MODERATE")


class Validation(unittest.TestCase):
    def test_required(self):
        ok, err = _validate_schema(
            {}, {"type": "object", "required": ["url"]})
        self.assertFalse(ok)
        self.assertIn("url", err)

    def test_type_mismatch(self):
        ok, err = _validate_schema(
            {"count": "not-a-number"},
            {"type": "object",
             "properties": {"count": {"type": "integer"}}})
        self.assertFalse(ok)
        self.assertIn("integer", err)

    def test_ok(self):
        ok, err = _validate_schema(
            {"url": "https://x.com"},
            {"type": "object",
             "properties": {"url": {"type": "string"}},
             "required": ["url"]})
        self.assertTrue(ok)

    def test_normalize_gemini_schema(self):
        params = {"type": "OBJECT",
                  "properties": {"url": {"type": "STRING"}},
                  "required": ["url"]}
        out = _normalize_schema(params)
        self.assertEqual(out["properties"]["url"]["type"], "string")
        self.assertEqual(out["required"], ["url"])


class Health(unittest.TestCase):
    def test_success_error_cycle(self):
        r = CapabilityRegistry()
        r.register(Capability(id="plugin.x"))
        r.report_success("plugin.x")
        self.assertEqual(r.get("plugin.x").health, "ok")
        r.report_error("plugin.x", "boom")
        r.report_error("plugin.x", "boom")
        r.report_error("plugin.x", "boom")
        self.assertEqual(r.get("plugin.x").health, "degraded")
        r.report_success("plugin.x")
        self.assertEqual(r.get("plugin.x").health, "ok")

    def test_mark_failed(self):
        r = CapabilityRegistry()
        r.register(Capability(id="plugin.y"))
        r.mark_failed("plugin.y", "hard down")
        self.assertEqual(r.get("plugin.y").health, "failed")


class GatewayPopulate(unittest.TestCase):
    def test_populates(self):
        reset_registry()
        r = get_registry()
        n = r.populate_from_gateway()
        self.assertGreater(n, 40, f"expected 40+ builtins, got {n}")
        d = r.by_tool_name("desktop")
        self.assertIsNotNone(d)
        self.assertEqual(d.risk.upper(), "HIGH")


if __name__ == "__main__":
    unittest.main()
