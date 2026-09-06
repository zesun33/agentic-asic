"""Gate 4 Integration Flow & Gate 6 Schema Contract Tests."""

import json
import os
import tempfile
import unittest
from agentic_asic.pipeline import ASICPipeline
from agentic_asic.reporter import SignoffReporter

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(ROOT_DIR, "fixtures")


class TestASICIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="asic_test_")

    def test_full_pipeline_pass_on_counter(self):
        counter_v = os.path.join(FIXTURES_DIR, "counter.v")
        counter_tb = os.path.join(FIXTURES_DIR, "counter_tb.v")
        counter_sdc = os.path.join(FIXTURES_DIR, "counter.sdc")

        pipeline = ASICPipeline(
            work_dir=self.temp_dir,
            clock_period_ns=2.0,
            core_utilization=0.35,
            target_pdk="generic",
        )
        out = pipeline.run(
            verilog_sources=[counter_v],
            top_module="counter",
            testbench=counter_tb,
            sdc_file=counter_sdc,
            do_pnr=True,
        )
        self.assertTrue(out["success"], f"Pipeline failed: {out.get('failing_stage')}")
        results = out["results"]
        self.assertTrue(results["review"].passed)
        self.assertTrue(results["simulate"].passed)
        self.assertTrue(results["synthesize"].passed)
        self.assertTrue(results["pnr"].passed)

        # Gate 6 schema verification
        json_report = SignoffReporter.generate_json_report(
            "counter", results, out["duration_seconds"], out["retries"]
        )
        self.assertEqual(json_report["signoff_status"], "PASS")
        self.assertEqual(json_report["schema_version"], "1.0.0")
        self.assertIn("review", json_report["stages"])
        self.assertIn("pnr", json_report["stages"])

    def test_pipeline_catches_bad_rtl(self):
        bad_v = os.path.join(FIXTURES_DIR, "counter_bad.v")
        pipeline = ASICPipeline(work_dir=self.temp_dir)
        out = pipeline.run(
            verilog_sources=[bad_v],
            top_module="counter_bad",
            do_pnr=False,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["failing_stage"], "review")
        self.assertFalse(out["results"]["review"].passed)


if __name__ == "__main__":
    unittest.main()
