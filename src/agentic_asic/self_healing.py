"""Closed-loop self-healing heuristics and LLM diagnosis generator."""

from typing import Any, Dict, List, Optional, Tuple


class SelfHealingEngine:
    """Heuristic optimizer and diagnostic generator for failed ASIC stages."""

    @staticmethod
    def recommend_pnr_relaxation(
        core_utilization: float,
        clock_period_ns: float,
        wns_ns: float,
        failure_type: str = "timing",
    ) -> Tuple[float, float, str]:
        """Calculates adjusted physical design parameters to heal timing or congestion.

        Returns (new_utilization, new_clock_period_ns, reason)
        """
        if failure_type == "congestion" or failure_type == "placement":
            new_util = max(0.15, round(core_utilization - 0.10, 2))
            return (
                new_util,
                clock_period_ns,
                f"Reduced core utilization from {core_utilization:.2f} to {new_util:.2f} to relieve routing congestion",
            )
        elif failure_type == "timing" and wns_ns < 0:
            # Relax clock period by slack deficit + 20% margin
            slack_deficit = abs(wns_ns)
            new_period = round(clock_period_ns + (slack_deficit * 1.25), 2)
            return (
                core_utilization,
                new_period,
                f"Relaxed clock period from {clock_period_ns:.2f}ns to {new_period:.2f}ns to overcome WNS slack deficit ({wns_ns:.2f}ns)",
            )
        else:
            # Combined fallback
            new_util = max(0.20, round(core_utilization - 0.05, 2))
            new_period = round(clock_period_ns * 1.20, 2)
            return (
                new_util,
                new_period,
                f"Adjusted utilization ({core_utilization:.2f} -> {new_util:.2f}) and period ({clock_period_ns:.2f}ns -> {new_period:.2f}ns)",
            )

    @staticmethod
    def generate_llm_repair_prompt(
        stage_name: str,
        error_message: str,
        rtl_code: Optional[str] = None,
        diagnostics: Optional[List[str]] = None,
    ) -> str:
        """Constructs an actionable prompt for an LLM agent to repair RTL or constraints."""
        diag_str = "\n".join([f"- {d}" for d in (diagnostics or [])])
        return (
            f"### ASIC Agent Repair Request: {stage_name.upper()} Stage Failure\n\n"
            f"**Failure Reason**: {error_message}\n\n"
            f"**Diagnostics Detected**:\n{diag_str if diag_str else '- None provided'}\n\n"
            f"**Remediation Instructions**:\n"
            f"1. Audit the RTL source code below to eliminate any sequential blocking assignments (`=`) or unintended latches.\n"
            f"2. Ensure all registers are clocked under a clean edge-triggered `always @(posedge clk)` block with asynchronous reset.\n"
            f"3. Return the corrected Verilog code block enclosed in triple backticks.\n\n"
            f"```verilog\n{rtl_code or '// RTL source omitted'}\n```\n"
        )
