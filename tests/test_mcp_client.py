"""Unit tests for MCPClientSession and MCPServerLocator."""

import unittest
from agentic_asic.mcp_client import MCPServerLocator
from agentic_asic.self_healing import SelfHealingEngine


class TestMCPClientAndSelfHealing(unittest.TestCase):
    def test_server_locator_resolves_all_8_servers(self):
        for s in ["review", "verilog", "cocotb", "yosys", "openroad", "gds", "formal", "fpga"]:
            cmd = MCPServerLocator.resolve(s)
            self.assertIsNotNone(cmd, f"Locator failed to resolve {s}")
            self.assertEqual(cmd[0], "node")
            self.assertTrue(cmd[1].endswith("index.js"))

    def test_self_healing_timing_relaxation(self):
        new_util, new_period, reason = SelfHealingEngine.recommend_pnr_relaxation(
            core_utilization=0.40,
            clock_period_ns=1.00,
            wns_ns=-0.50,
            failure_type="timing",
        )
        self.assertEqual(new_util, 0.40)
        self.assertGreater(new_period, 1.00)
        self.assertIn("overcome WNS slack deficit", reason)

    def test_self_healing_timing_has_half_ns_floor(self):
        new_util, new_period, reason = SelfHealingEngine.recommend_pnr_relaxation(
            core_utilization=0.35,
            clock_period_ns=10.00,
            wns_ns=-0.04,
            failure_type="timing",
        )
        self.assertEqual(new_util, 0.35)
        self.assertGreaterEqual(new_period, 10.50)

    def test_self_healing_congestion_relaxation(self):
        new_util, new_period, reason = SelfHealingEngine.recommend_pnr_relaxation(
            core_utilization=0.50,
            clock_period_ns=2.00,
            wns_ns=0.0,
            failure_type="congestion",
        )
        self.assertLess(new_util, 0.50)
        self.assertEqual(new_period, 2.00)
        self.assertIn("relieve routing congestion", reason)

    def test_apply_clock_period_to_sdc_rewrites_create_clock(self):
        sdc = "create_clock -name clk -period 2.000 [get_ports clk]\n"
        out = SelfHealingEngine.apply_clock_period_to_sdc(sdc, 7.26)
        self.assertIn("-period 7.260", out)
        self.assertNotIn("2.000", out)

    def test_apply_clock_period_to_sdc_rejects_missing_clock(self):
        with self.assertRaises(ValueError):
            SelfHealingEngine.apply_clock_period_to_sdc("# empty\n", 10.0)

    def test_llm_repair_prompt_generation(self):
        prompt = SelfHealingEngine.generate_llm_repair_prompt(
            stage_name="synthesize",
            error_message="Inferred latch detected",
            rtl_code="always @(*) if (en) q = d;",
            diagnostics=["Missing else clause for q"],
        )
        self.assertIn("SYNTHESIZE", prompt)
        self.assertIn("Missing else clause", prompt)
        self.assertIn("always @(*)", prompt)


if __name__ == "__main__":
    unittest.main()
