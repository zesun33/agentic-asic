"""Terminal dashboard and signoff report exporter (Markdown & JSON)."""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from agentic_asic.stages import (
    FormalStageResult,
    FpgaStageResult,
    PnRStageResult,
    ReviewStageResult,
    SignoffStageResult,
    SimStageResult,
    StageResult,
    SynthStageResult,
)


_HASH_RE = re.compile(r"Logfile hash: [0-9a-f]+")
_TIME_RE = re.compile(r"^Time spent:.*$", re.MULTILINE)
_CPU_RE = re.compile(r", CPU: user .* system .* MEM: .* peak")


def sanitize_nondeterminism(value):
    """Strips run-varying tool chatter (hashes, CPU timings) so reports
    and golden transcripts are byte-stable across identical runs."""
    if isinstance(value, str):
        value = _HASH_RE.sub("Logfile hash: <hash>", value)
        value = _TIME_RE.sub("Time spent: <timing>", value)
        return _CPU_RE.sub("", value)
    if isinstance(value, list):
        return [sanitize_nondeterminism(v) for v in value]
    if isinstance(value, dict):
        return {k: sanitize_nondeterminism(v) for k, v in value.items()}
    return value


class SignoffReporter:
    """Formats and exports unified ASIC signoff reports."""

    @staticmethod
    def print_terminal_dashboard(
        design_name: str,
        results: Dict[str, StageResult],
        total_duration_s: float,
        retries: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        passed_all = len(results) > 0 and all(r.passed for r in results.values())

        print("\n\033[1;36m=======================================================================\033[0m")
        print("\033[1;36m                      agentic-asic Signoff Dashboard                   \033[0m")
        print("\033[1;36m=======================================================================\033[0m")
        print(f"  Design Module : \033[1m{design_name}\033[0m")
        print(f"  Run Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        print(f"  Duration      : {total_duration_s:.2f} seconds (Self-healing retries: {retries})")
        print("  ---------------------------------------------------------------------")
        print(f"  {'Stage':<18} {'Status':<12} {'Key Metric / Detail'}")
        print("  ---------------------------------------------------------------------")

        # Stage 1: Review
        rev = results.get("review")
        if isinstance(rev, ReviewStageResult):
            status = "\033[1;32mPASSED\033[0m" if rev.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'1. AST Review':<27} {status:<20} Score: {rev.score}/100, Violations: {len(rev.violations)}")

        # Stage 2: Sim
        sim = results.get("simulate")
        if isinstance(sim, SimStageResult):
            status = "\033[1;32mPASSED\033[0m" if sim.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'2. Simulation':<27} {status:<20} {sim.simulator}: {sim.tests_passed}/{sim.tests_run} tests passed")

        # Stage 3: Synth
        synth = results.get("synthesize")
        if isinstance(synth, SynthStageResult):
            status = "\033[1;32mPASSED\033[0m" if synth.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'3. Logic Synth':<27} {status:<20} Cells: {synth.total_cells}, Inferred Latches: {len(synth.inferred_latches)}")

        # Stage 4: PnR
        pnr = results.get("pnr")
        if isinstance(pnr, PnRStageResult):
            status = "\033[1;32mPASSED\033[0m" if pnr.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'4. Physical P&R':<27} {status:<20} WNS: {pnr.wns_ns:.2f}ns, Util: {pnr.core_utilization:.2f}")

        # Stage 5: Formal (only when RTL carries asserts)
        formal = results.get("formal")
        if isinstance(formal, FormalStageResult):
            status = "\033[1;32mPASSED\033[0m" if formal.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'5. Formal':<27} {status:<20} Verdict: {formal.verdict}, Failed asserts: {len(formal.failed_assertions)}")

        # Stage 6: Signoff (only when P&R ran)
        signoff = results.get("signoff")
        if isinstance(signoff, SignoffStageResult):
            status = "\033[1;32mPASSED\033[0m" if signoff.passed else "\033[1;31mFAILED\033[0m"
            print(f"  {'6. GDS Signoff':<27} {status:<20} DRC findings: {signoff.drc_violations} (clean: {signoff.drc_clean}, LVS: {signoff.lvs_match})")

        if error_message:
            print(f"  Config error: {error_message}")
        print("  ---------------------------------------------------------------------")
        if passed_all:
            print("  \033[1;32m✔ FINAL ASIC SIGNOFF VERDICT: TAPE-OUT READY (ALL GATES PASSED)\033[0m")
        else:
            print("  \033[1;31m✖ FINAL ASIC SIGNOFF VERDICT: VIOLATION (REPAIR REQUIRED)\033[0m")
        print("\033[1;36m=======================================================================\033[0m\n")

    @staticmethod
    def print_fpga_dashboard(
        design_name: str,
        result: "FpgaStageResult",
        total_duration_s: float,
    ) -> None:
        from agentic_asic.stages import FpgaStageResult as _FpgaRes

        print("\n\033[1;36m=======================================================================\033[0m")
        print("\033[1;36m                      agentic-asic FPGA Flow                        \033[0m")
        print("\033[1;36m=======================================================================\033[0m")
        print(f"  Design Module : \033[1m{design_name}\033[0m")
        print(f"  Board         : {result.board}")
        print(f"  Duration      : {total_duration_s:.2f} seconds")
        print("  ---------------------------------------------------------------------")
        status = "\033[1;32mPASSED\033[0m" if result.passed else "\033[1;31mFAILED\033[0m"
        detail = result.bitstream_file or (result.error_message or "")
        print(f"  {'FPGA flow':<27} {status:<20} {detail}")
        if isinstance(result, _FpgaRes) and result.fmax_mhz is not None:
            print(f"  {'Fmax':<27} {'':<20} {result.fmax_mhz:.2f} MHz")
        for d in result.diagnostics:
            print(f"  - {d}")
        print("\033[1;36m=======================================================================\033[0m\n")

    @staticmethod
    def generate_json_report(
        design_name: str,
        results: Dict[str, StageResult],
        total_duration_s: float,
        retries: int = 0,
    ) -> Dict[str, Any]:
        """Builds a deterministic JSON dictionary conforming to the signoff schema."""
        passed_all = len(results) > 0 and all(r.passed for r in results.values())
        stages_data: Dict[str, Any] = {}

        for name, r in results.items():
            stages_data[name] = {
                "passed": r.passed,
                "error_message": r.error_message,
                "diagnostics": r.diagnostics,
                "details": sanitize_nondeterminism(r.details),
            }
            if isinstance(r, ReviewStageResult):
                stages_data[name]["score"] = r.score
                stages_data[name]["violations"] = r.violations
            elif isinstance(r, SimStageResult):
                stages_data[name]["simulator"] = r.simulator
                stages_data[name]["tests_run"] = r.tests_run
                stages_data[name]["tests_passed"] = r.tests_passed
            elif isinstance(r, SynthStageResult):
                stages_data[name]["target"] = r.target
                stages_data[name]["total_cells"] = r.total_cells
                stages_data[name]["cell_counts"] = r.cell_counts
                stages_data[name]["inferred_latches"] = r.inferred_latches
                stages_data[name]["netlist_file"] = r.netlist_file
                stages_data[name]["spice_file"] = r.spice_file
            elif isinstance(r, PnRStageResult):
                stages_data[name]["wns_ns"] = r.wns_ns
                stages_data[name]["tns_ns"] = r.tns_ns
                stages_data[name]["clock_period_ns"] = r.clock_period_ns
                stages_data[name]["core_utilization"] = r.core_utilization
                stages_data[name]["platform"] = r.platform
                stages_data[name]["def_file"] = r.def_file
            elif isinstance(r, FormalStageResult):
                stages_data[name]["verdict"] = r.verdict
                stages_data[name]["failed_assertions"] = r.failed_assertions
            elif isinstance(r, SignoffStageResult):
                stages_data[name]["gds_file"] = r.gds_file
                stages_data[name]["drc_violations"] = r.drc_violations
                stages_data[name]["drc_clean"] = r.drc_clean
                stages_data[name]["lvs_match"] = r.lvs_match
            elif isinstance(r, FpgaStageResult):
                stages_data[name]["board"] = r.board
                stages_data[name]["bitstream_file"] = r.bitstream_file
                stages_data[name]["utilization"] = r.utilization
                stages_data[name]["fmax_mhz"] = r.fmax_mhz

        return {
            "schema_version": "1.1.0",
            "tool": "agentic-asic",
            "design": design_name,
            "signoff_status": "PASS" if passed_all else "FAIL",
            "total_duration_seconds": round(total_duration_s, 2),
            "self_healing_retries": retries,
            "stages": stages_data,
        }

    @staticmethod
    def generate_markdown_report(
        design_name: str,
        results: Dict[str, StageResult],
        total_duration_s: float,
        retries: int = 0,
    ) -> str:
        """Generates a GitHub-ready Markdown report."""
        passed_all = len(results) > 0 and all(r.passed for r in results.values())
        badge = "🟢 **PASS: TAPE-OUT READY**" if passed_all else "🔴 **FAIL: VIOLATIONS DETECTED**"

        lines = [
            f"# ASIC Signoff Tapeout Report: `{design_name}`",
            "",
            f"**Signoff Verdict**: {badge}  ",
            f"**Run Duration**: {total_duration_s:.2f}s (Heuristic Retries: {retries})  ",
            f"**Orchestrator**: `agentic-asic` v0.2.0 (Model Context Protocol)  ",
            "",
            "## 1. Stage Signoff Summary",
            "",
            "| Stage | MCP Server | Status | Metrics / Notes |",
            "| :--- | :--- | :---: | :--- |",
        ]

        rev = results.get("review")
        if isinstance(rev, ReviewStageResult):
            status = "✔ PASS" if rev.passed else "✖ FAIL"
            lines.append(f"| **1. AST Review** | `@zesun33/mcp-rtl-review` | `{status}` | Score: {rev.score}/100, Violations: {len(rev.violations)} |")

        sim = results.get("simulate")
        if isinstance(sim, SimStageResult):
            status = "✔ PASS" if sim.passed else "✖ FAIL"
            lines.append(f"| **2. Simulation** | `@zesun33/mcp-verilog` / `cocotb` | `{status}` | {sim.simulator}: {sim.tests_passed}/{sim.tests_run} test(s) passed |")

        synth = results.get("synthesize")
        if isinstance(synth, SynthStageResult):
            status = "✔ PASS" if synth.passed else "✖ FAIL"
            lines.append(f"| **3. Logic Synth** | `@zesun33/mcp-yosys` | `{status}` | Cells: {synth.total_cells}, Latches: {len(synth.inferred_latches)} |")

        pnr = results.get("pnr")
        if isinstance(pnr, PnRStageResult):
            status = "✔ PASS" if pnr.passed else "✖ FAIL"
            lines.append(f"| **4. Physical P&R** | `@zesun33/mcp-openroad` | `{status}` | WNS: {pnr.wns_ns:.2f}ns, Util: {pnr.core_utilization:.2f} |")

        formal = results.get("formal")
        if isinstance(formal, FormalStageResult):
            status = "✔ PASS" if formal.passed else "✖ FAIL"
            lines.append(f"| **5. Formal** | `@zesun33/mcp-formal` | `{status}` | Verdict: {formal.verdict} |")

        signoff = results.get("signoff")
        if isinstance(signoff, SignoffStageResult):
            status = "✔ PASS" if signoff.passed else "✖ FAIL"
            lines.append(f"| **6. GDS Signoff** | `@zesun33/mcp-gds` | `{status}` | DRC findings: {signoff.drc_violations}, LVS vs synth: {signoff.lvs_match} |")

        lines.extend([
            "",
            "## 2. Stage Details",
            "",
        ])

        if isinstance(rev, ReviewStageResult):
            lines.append("### Stage 1: AST Review & Code Quality")
            lines.append(f"- **Quality Score**: `{rev.score} / 100`")
            if rev.violations:
                lines.append("- **Violations**:")
                for v in rev.violations:
                    lines.append(f"  - `[Line {v.get('line', '?')}]` {v.get('rule')}: {v.get('message')}")
            else:
                lines.append("- **Violations**: Zero detected (Clean RTL)")
            lines.append("")

        if isinstance(synth, SynthStageResult):
            lines.append("### Stage 3: Logic Synthesis & Cell Breakdown")
            lines.append(f"- **Total Logic Cells**: `{synth.total_cells}`")
            lines.append(f"- **Inferred Latches**: `{len(synth.inferred_latches)}`")
            if synth.cell_counts:
                lines.append("- **Gate Breakdown**:")
                for cell, cnt in synth.cell_counts.items():
                    lines.append(f"  - `{cell}`: {cnt}")
            lines.append("")

        if isinstance(formal, FormalStageResult):
            lines.append("### Stage 5: Formal Property Verification")
            lines.append(f"- **Verdict**: `{formal.verdict}`")
            if formal.failed_assertions:
                lines.append("- **Counterexamples**:")
                for fa in formal.failed_assertions:
                    lines.append(f"  - `{fa.get('name', '?')}` at `{fa.get('location', '?')}` (step {fa.get('step', '?')})")
            lines.append("")

        if isinstance(signoff, SignoffStageResult):
            lines.append("### Stage 6: GDSII Stream-Out & DRC Smoke")
            lines.append(f"- **GDS File**: `{signoff.gds_file}`")
            lines.append(f"- **DRC Findings**: `{signoff.drc_violations}` (clean: `{signoff.drc_clean}`)")
            lines.append("")

        if isinstance(pnr, PnRStageResult):
            lines.append("### Stage 4: Physical Design & Static Timing Analysis")
            lines.append(f"- **Worst Negative Slack (WNS)**: `{pnr.wns_ns:.2f} ns`")
            lines.append(f"- **Total Negative Slack (TNS)**: `{pnr.tns_ns:.2f} ns`")
            lines.append(f"- **Core Utilization Target**: `{pnr.core_utilization * 100:.1f}%`")
            lines.append(f"- **Clock Period Target**: `{pnr.clock_period_ns:.2f} ns`")
            lines.append("")

        lines.extend([
            "## 3. Autonomous Signoff Recommendation",
            "",
            "The design is verified against all structural, functional, synthesis, and physical layout constraints." if passed_all else "Remediate errors indicated above prior to physical fabrication.",
            "",
        ])

        return "\n".join(lines)
