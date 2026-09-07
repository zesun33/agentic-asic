"""Closed-loop self-healing heuristics and LLM diagnosis generator."""

import re
from typing import Dict, List, Optional, Tuple

_CREATE_CLOCK_PERIOD = re.compile(
    r"(create_clock\b[^\n]*?-period\s+)([0-9.]+)",
    re.IGNORECASE,
)


class SelfHealingEngine:
    """Heuristic optimizer and diagnostic generator for failed ASIC stages."""

    @staticmethod
    def apply_clock_period_to_sdc(sdc_text: str, period_ns: float) -> str:
        """Rewrite the first create_clock -period so CLI/heal period actually applies.

        read_sdc wins over openroad_pnr's clock_period_ns, so a stale SDC file
        makes timing retries no-ops (same WNS, same 2 ns clock, three times).
        """
        new, n = _CREATE_CLOCK_PERIOD.subn(
            lambda m: f"{m.group(1)}{period_ns:.3f}",
            sdc_text,
            count=1,
        )
        if n == 0:
            raise ValueError("SDC has no create_clock -period to update")
        return new

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
            # Relax clock period by slack deficit + 25%, with a 0.5 ns floor
            # so a -0.04 ns miss does not burn a full P&R for +0.05 ns.
            slack_deficit = abs(wns_ns)
            bump = max(slack_deficit * 1.25, 0.50)
            new_period = round(clock_period_ns + bump, 2)
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
