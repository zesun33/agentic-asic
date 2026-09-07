"""Unit tests for the v0.2 formal, signoff, and FPGA stages (stub sessions, no containers)."""

import os
import tempfile
import unittest
from agentic_asic.stages.formal import run_formal_stage, detect_assertions
from agentic_asic.stages.signoff import run_signoff_stage
from agentic_asic.stages.fpga import run_fpga_flow


class StubSession:
    """Minimal MCPClientSession double returning canned tool payloads."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        payload = self.payloads.get(name)
        if isinstance(payload, Exception):
            raise payload
        return payload

    def close(self):
        pass


class TestFormalStage(unittest.TestCase):
    def test_proven_passes(self):
        sess = StubSession({
            "formal_prove": {"success": True, "verdict": "PROVEN", "failedAssertions": []},
        })
        res = run_formal_stage(["a.v"], "top", session=sess)
        self.assertTrue(res.passed)
        self.assertEqual(res.verdict, "PROVEN")
        self.assertEqual(sess.calls[0][0], "formal_prove")

    def test_failed_blocks_with_diagnostics(self):
        sess = StubSession({
            "formal_prove": {
                "success": True,
                "verdict": "FAILED",
                "failedAssertions": [{"name": "top.$assert$a", "location": "a.v:3", "step": 1}],
            },
        })
        res = run_formal_stage(["a.v"], "top", session=sess)
        self.assertFalse(res.passed)
        self.assertEqual(res.verdict, "FAILED")
        self.assertTrue(any("a.v:3" in d for d in res.diagnostics))

    def test_unresolvable_server_fails(self):
        from agentic_asic import mcp_client

        orig = mcp_client.MCPServerLocator.resolve
        mcp_client.MCPServerLocator.resolve = classmethod(lambda cls, key: None)
        try:
            res = run_formal_stage(["a.v"], "top")
            self.assertFalse(res.passed)
            self.assertIn("mcp-formal", res.error_message)
        finally:
            mcp_client.MCPServerLocator.resolve = orig

    def test_detect_assertions(self):
        d = tempfile.mkdtemp(prefix="formal_detect_")
        clean = os.path.join(d, "clean.v")
        with open(clean, "w") as f:
            f.write("module c(input clk, output reg q);\nalways @(posedge clk) q <= 1'b0;\nendmodule\n")
        prop = os.path.join(d, "prop.sv")
        with open(prop, "w") as f:
            f.write("module p(input clk, input [3:0] c);\nalways @(posedge clk) assert (c < 16);\nendmodule\n")
        tb = os.path.join(d, "stim_tb.v")
        with open(tb, "w") as f:
            f.write("module t; initial begin $assertkill(0); $finish; end endmodule\n")
        self.assertFalse(detect_assertions(["clean.v"], d))
        self.assertTrue(detect_assertions(["prop.sv"], d))
        self.assertFalse(detect_assertions(["stim_tb.v"], d))
        self.assertFalse(detect_assertions(["missing.v"], d))


class TestSignoffStage(unittest.TestCase):
    def test_pass_reports_drc_findings_as_diagnostics(self):
        sess = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {
                "success": True,
                "violations": [{"rule": "W_31/0", "count": 2}],
                "totalViolations": 2,
                "clean": False,
            },
        })
        res = run_signoff_stage("top_routed.def", "top", session=sess)
        self.assertTrue(res.passed)
        self.assertEqual(res.gds_file, "top.gds")
        self.assertEqual(res.drc_violations, 2)
        self.assertFalse(res.drc_clean)
        self.assertTrue(any("W_31/0" in d for d in res.diagnostics))

    def test_stream_failure_fails_stage(self):
        sess = StubSession({
            "gds_stream_out": {"success": False, "errors": ["no DEF"]},
        })
        res = run_signoff_stage("missing.def", "top", session=sess)
        self.assertFalse(res.passed)
        self.assertIn("stream-out", res.error_message)


class TestFpgaFlow(unittest.TestCase):
    def test_full_chain_to_bitstream(self):
        sess = StubSession({
            "fpga_synth": {"success": True, "jsonNetlist": "b.json", "cellCount": 30},
            "fpga_place_route": {
                "success": True,
                "outputFile": "b.asc",
                "utilization": {"ICESTORM_LC": {"available": 7680, "used": 28}},
                "fmax": {"clk": {"achievedMhz": 150.0}},
            },
            "fpga_bitstream": {"success": True, "bitstreamFile": "b.bin", "bytes": 1000},
            "fpga_program": {"success": True, "programmer": "iceprog", "flashed": False},
        })
        res = run_fpga_flow(["b.v"], "blink", board="icebreaker", session=sess)
        self.assertTrue(res.passed)
        self.assertEqual(res.bitstream_file, "b.bin")
        self.assertEqual(res.fmax_mhz, 150.0)
        self.assertEqual([c[0] for c in sess.calls],
                         ["fpga_synth", "fpga_place_route", "fpga_bitstream", "fpga_program"])

    def test_synth_failure_short_circuits(self):
        sess = StubSession({
            "fpga_synth": {"success": False, "errors": ["boom"]},
        })
        res = run_fpga_flow(["b.v"], "blink", session=sess)
        self.assertFalse(res.passed)
        self.assertEqual(len(sess.calls), 1)


if __name__ == "__main__":
    unittest.main()
