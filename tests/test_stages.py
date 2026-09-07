"""Unit tests for the v0.2 formal, signoff, and FPGA stages (stub sessions, no containers)."""

import json
import os
import tempfile
import unittest
from agentic_asic.stages.formal import run_formal_stage, detect_assertions
from agentic_asic.stages.signoff import run_signoff_stage
from agentic_asic.stages.synthesize import run_synthesize_stage
from agentic_asic.stages.pnr import run_pnr_stage
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

    def test_pdk_forwarded_to_drc_only_when_given(self):
        sess = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {"success": True, "violations": [], "totalViolations": 0, "clean": True},
        })
        res = run_signoff_stage("top_routed.def", "top", pdk="sky130A", session=sess)
        self.assertTrue(res.passed)
        drc_calls = [c for c in sess.calls if c[0] == "drc_klayout"]
        self.assertEqual(len(drc_calls), 1)
        self.assertEqual(drc_calls[0][1].get("pdk"), "sky130A")
        stream_calls = [c for c in sess.calls if c[0] == "gds_stream_out"]
        self.assertEqual(len(stream_calls), 1)
        self.assertEqual(stream_calls[0][1].get("pdk"), "sky130A")

        sess2 = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {"success": True, "violations": [], "totalViolations": 0, "clean": True},
        })
        run_signoff_stage("top_routed.def", "top", session=sess2)
        drc_calls2 = [c for c in sess2.calls if c[0] == "drc_klayout"]
        self.assertNotIn("pdk", drc_calls2[0][1])

    def test_extract_lvs_wiring_reports_match(self):
        sess = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {"success": True, "violations": [], "totalViolations": 0, "clean": True},
            "extract_magic": {"success": True, "spiceFile": "top_layout.spice"},
            "lvs_netgen": {"success": True, "match": True},
        })
        res = run_signoff_stage("top_routed.def", "top", netlist_file="top_synth.v", pdk="sky130A", session=sess)
        self.assertTrue(res.passed)
        self.assertTrue(res.lvs_match)
        self.assertEqual(res.layout_spice, "top_layout.spice")
        self.assertTrue(any("LVS" in d and "MATCH" in d for d in res.diagnostics))
        tools_called = [c[0] for c in sess.calls]
        self.assertIn("extract_magic", tools_called)
        self.assertIn("lvs_netgen", tools_called)
        ext_calls = [c for c in sess.calls if c[0] == "extract_magic"]
        self.assertEqual(ext_calls[0][1].get("cell"), "top")

    def test_lvs_skipped_without_pdk(self):
        sess = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {"success": True, "violations": [], "totalViolations": 0, "clean": True},
        })
        res = run_signoff_stage("top_routed.def", "top", netlist_file="top_synth.v", session=sess)
        self.assertTrue(res.passed)
        self.assertIsNone(res.lvs_match)
        tools_called = [c[0] for c in sess.calls]
        self.assertNotIn("extract_magic", tools_called)
        self.assertTrue(any("LVS skipped" in d for d in res.diagnostics))

    def test_lvs_mismatch_does_not_fail_stage_yet(self):
        sess = StubSession({
            "gds_stream_out": {"success": True, "gdsFile": "top.gds", "cellsWritten": 14},
            "drc_klayout": {"success": True, "violations": [], "totalViolations": 0, "clean": True},
            "extract_magic": {"success": True, "spiceFile": "top_layout.spice"},
            "lvs_netgen": {"success": True, "match": False},
        })
        res = run_signoff_stage("top_routed.def", "top", netlist_file="top_synth.v", pdk="sky130A", session=sess)
        self.assertTrue(res.passed)
        self.assertFalse(res.lvs_match)


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

class TestSanitizeNondeterminism(unittest.TestCase):
    def test_strips_hashes_timings_and_cpu(self):
        from agentic_asic.reporter import sanitize_nondeterminism

        raw = {
            "rawStdout": "End of script. Logfile hash: d3662c29, CPU: user 0.19s system 0.02s, MEM: 28.75 MB peak\nTime spent: 45% 2x abc (0 sec)\nreal result 42\n",
            "nested": ["Time spent: 1x opt (9 sec)", "keep me"],
        }
        clean = sanitize_nondeterminism(raw)
        text = json.dumps(clean)
        self.assertNotIn("d3662c29", text)
        self.assertNotIn("0.19s", text)
        self.assertIn("Logfile hash: <hash>", text)
        self.assertIn("Time spent: <timing>", text)
        self.assertIn("real result 42", text)
        self.assertIn("keep me", text)
        # Idempotent
        self.assertEqual(sanitize_nondeterminism(clean), clean)


if __name__ == "__main__":
    unittest.main()


class TestSynthSpiceExport(unittest.TestCase):
    def _sess(self):
        return StubSession({
            "yosys_check_latch": {"hasLatches": False, "latches": []},
            "yosys_synthesize": {"success": True, "cellsByType": {"x": 1}, "cellCount": 1, "netlistPath": "top_synth.v"},
            "yosys_write_spice": {"success": True, "spiceFile": "top_synth.spice", "cellCount": 1},
        })

    def test_spice_export_called_when_requested(self):
        sess = self._sess()
        res = run_synthesize_stage(["a.v"], "top", target="sky130", output_netlist="top_synth.v",
                                   output_spice="top_synth.spice", session=sess)
        self.assertTrue(res.passed)
        self.assertEqual(res.spice_file, "top_synth.spice")
        tools = [c[0] for c in sess.calls]
        self.assertIn("yosys_write_spice", tools)

    def test_no_spice_call_without_output_spice(self):
        sess = self._sess()
        res = run_synthesize_stage(["a.v"], "top", target="nangate45", output_netlist="top_synth.v", session=sess)
        self.assertTrue(res.passed)
        self.assertIsNone(res.spice_file)
        tools = [c[0] for c in sess.calls]
        self.assertNotIn("yosys_write_spice", tools)


class TestPnrDetailRoute(unittest.TestCase):
    def test_detail_route_and_platform_forwarded(self):
        sess = StubSession({
            "openroad_pnr": {"success": True, "timing": {"wns": 0.1, "tns": 0.0, "timingMet": True}, "defFile": "top_routed.def"},
        })
        res = run_pnr_stage("top_synth.v", "top", platform="sky130", detail_route=True, session=sess)
        self.assertTrue(res.passed)
        self.assertEqual(res.platform, "sky130")
        pnr_calls = [c for c in sess.calls if c[0] == "openroad_pnr"]
        self.assertEqual(len(pnr_calls), 1)
        self.assertEqual(pnr_calls[0][1].get("platform"), "sky130")
        self.assertTrue(pnr_calls[0][1].get("detail_route"))
