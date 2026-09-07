"""Gate 4 Integration Flow & Gate 6 Schema Contract Tests."""

import json
import os
import tempfile
import unittest
from agentic_asic.pipeline import ASICPipeline
from agentic_asic.reporter import SignoffReporter
from agentic_asic.stages.fpga import run_fpga_flow

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
            target_pdk="nangate45",
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
        self.assertEqual(json_report["schema_version"], "1.1.0")
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

    def test_pipeline_halts_on_inferred_latch(self):
        latch_v = os.path.join(FIXTURES_DIR, "latch_demo.v")
        pipeline = ASICPipeline(work_dir=self.temp_dir)
        out = pipeline.run(
            verilog_sources=[latch_v],
            top_module="latch_demo",
            do_pnr=False,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["failing_stage"], "synthesize")
        synth_res = out["results"]["synthesize"]
        self.assertFalse(synth_res.passed)
        self.assertGreater(len(synth_res.inferred_latches), 0)

    def test_full_pipeline_on_alu(self):
        alu_v = os.path.join(FIXTURES_DIR, "alu.v")
        alu_tb = os.path.join(FIXTURES_DIR, "alu_tb.v")
        pipeline = ASICPipeline(
            work_dir=self.temp_dir,
            clock_period_ns=2.0,
            core_utilization=0.35,
            target_pdk="nangate45",
        )
        out = pipeline.run(
            verilog_sources=[alu_v],
            top_module="alu",
            testbench=alu_tb,
            do_pnr=True,
        )
        self.assertTrue(out["success"], f"ALU Pipeline failed: {out.get('failing_stage')}")
        results = out["results"]
        self.assertTrue(results["review"].passed)
        self.assertTrue(results["simulate"].passed)
        self.assertTrue(results["synthesize"].passed)
        self.assertGreater(results["synthesize"].total_cells, 100)
        self.assertTrue(results["pnr"].passed)


    def test_pipeline_skips_formal_without_asserts(self):
        counter_v = os.path.join(FIXTURES_DIR, "counter.v")
        pipeline = ASICPipeline(work_dir=self.temp_dir)
        out = pipeline.run(
            verilog_sources=[counter_v],
            top_module="counter",
            do_pnr=False,
        )
        self.assertTrue(out["success"])
        self.assertNotIn("formal", out["results"])

    def test_pipeline_rejects_generic_with_pnr(self):
        counter_v = os.path.join(FIXTURES_DIR, "counter.v")
        pipeline = ASICPipeline(work_dir=self.temp_dir, target_pdk="generic")
        out = pipeline.run(
            verilog_sources=[counter_v],
            top_module="counter",
            do_pnr=True,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["failing_stage"], "config")

    def test_pipeline_proves_assert_fixture(self):
        prop_v = os.path.join(FIXTURES_DIR, "counter_assert.sv")
        prop_tb = os.path.join(FIXTURES_DIR, "counter_assert_tb.v")
        pipeline = ASICPipeline(work_dir=self.temp_dir)
        out = pipeline.run(
            verilog_sources=[prop_v],
            top_module="counter_assert",
            testbench=prop_tb,
            do_pnr=False,
        )
        self.assertTrue(out["success"], f"Pipeline failed: {out.get('failing_stage')}")
        self.assertIn("formal", out["results"])
        formal_res = out["results"]["formal"]
        self.assertTrue(formal_res.passed)
        self.assertEqual(formal_res.verdict, "PROVEN")

    def test_pipeline_refutes_bad_assert_fixture(self):
        prop_v = os.path.join(FIXTURES_DIR, "counter_assert_bad.sv")
        pipeline = ASICPipeline(work_dir=self.temp_dir)
        out = pipeline.run(
            verilog_sources=[prop_v],
            top_module="counter_assert_bad",
            do_pnr=False,
        )
        self.assertFalse(out["success"])
        self.assertEqual(out["failing_stage"], "formal")
        self.assertIn("formal", out["results"])
        formal_res = out["results"]["formal"]
        self.assertFalse(formal_res.passed)
        self.assertEqual(formal_res.verdict, "FAILED")

    def test_pipeline_signoff_after_pnr(self):
        counter_v = os.path.join(FIXTURES_DIR, "counter.v")
        counter_tb = os.path.join(FIXTURES_DIR, "counter_tb.v")
        counter_sdc = os.path.join(FIXTURES_DIR, "counter.sdc")
        pipeline = ASICPipeline(
            work_dir=self.temp_dir,
            clock_period_ns=2.0,
            core_utilization=0.35,
            target_pdk="nangate45",
        )
        out = pipeline.run(
            verilog_sources=[counter_v],
            top_module="counter",
            testbench=counter_tb,
            sdc_file=counter_sdc,
            do_pnr=True,
        )
        self.assertTrue(out["success"], f"Pipeline failed: {out.get('failing_stage')}")
        self.assertIn("signoff", out["results"])
        signoff_res = out["results"]["signoff"]
        self.assertTrue(signoff_res.passed)
        self.assertTrue(signoff_res.gds_file)
        self.assertTrue(
            os.path.isfile(os.path.join(self.temp_dir, signoff_res.gds_file)),
            "Signoff GDS artifact missing",
        )

    def test_fpga_flow_icebreaker(self):
        blink_v = os.path.join(FIXTURES_DIR, "blink.v")
        res = run_fpga_flow(
            verilog_sources=[blink_v],
            top_module="blink",
            board="icebreaker",
            cwd=self.temp_dir,
        )
        self.assertTrue(res.passed, f"FPGA flow failed: {res.error_message}")
        self.assertTrue(res.bitstream_file)
        self.assertTrue(
            os.path.isfile(os.path.join(self.temp_dir, res.bitstream_file)),
            "FPGA bitstream artifact missing",
        )


if __name__ == "__main__":
    unittest.main()
