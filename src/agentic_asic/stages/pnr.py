"""Stage 4: Physical Design & Static Timing Analysis via @zesun33/mcp-openroad."""

import os
from typing import Any, Dict, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import PnRStageResult


def _relpath_if_possible(p: str, start: Optional[str]) -> str:
    if not start or not p:
        return p
    try:
        abs_p = os.path.abspath(p)
        abs_start = os.path.abspath(start)
        if abs_p.startswith(abs_start):
            return os.path.relpath(abs_p, abs_start)
    except Exception:
        pass
    return p


def run_pnr_stage(
    netlist_file: str,
    top_module: str,
    clock_period_ns: float = 2.0,
    core_utilization: float = 0.70,
    output_def: Optional[str] = None,
    sdc_file: Optional[str] = None,
    platform: str = "nangate45",
    detail_route: bool = False,
    cwd: Optional[str] = None,
    session: Optional[MCPClientSession] = None,
) -> PnRStageResult:
    """Runs automated placement, routing, and static timing analysis with OpenROAD."""
    norm_netlist = _relpath_if_possible(netlist_file, cwd)
    norm_def = _relpath_if_possible(output_def, cwd) if output_def else None
    norm_sdc = _relpath_if_possible(sdc_file, cwd) if sdc_file else None

    owns_session = False
    if session is None:
        cmd = MCPServerLocator.resolve("openroad")
        if not cmd:
            return PnRStageResult(
                stage_name="pnr",
                passed=False,
                error_message="Could not resolve @zesun33/mcp-openroad executable",
            )
        session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        args: Dict[str, Any] = {
            "netlist_file": norm_netlist,
            "top_module": top_module,
            "clock_period_ns": clock_period_ns,
            "core_utilization": core_utilization,
            "platform": platform,
            "detail_route": detail_route,
        }
        if norm_def:
            args["output_def"] = norm_def
        if norm_sdc:
            args["sdc_file"] = norm_sdc
        if cwd:
            args["cwd"] = cwd

        res = session.call_tool("openroad_pnr", args)
        if not isinstance(res, dict):
            return PnRStageResult(
                stage_name="pnr",
                passed=False,
                clock_period_ns=clock_period_ns,
                core_utilization=core_utilization,
                error_message=f"Invalid response from openroad_pnr: {res}",
            )

        passed = res.get("success", res.get("passed", False))
        timing = res.get("timing") or res.get("metrics") or {}
        wns = float(timing.get("wns", 0.0))
        tns = float(timing.get("tns", 0.0))
        timing_met = timing.get("timingMet", timing.get("timing_met", wns >= 0.0))
        def_path = res.get("defFile") or res.get("output_def") or output_def

        return PnRStageResult(
            stage_name="pnr",
            passed=passed and timing_met,
            clock_period_ns=clock_period_ns,
            core_utilization=core_utilization,
            platform=platform,
            wns_ns=wns,
            tns_ns=tns,
            def_file=def_path,
            timing_met=timing_met,
            details={"pnr": res},
            error_message=None if (passed and timing_met) else f"PnR failed or timing violation: WNS={wns} ns",
        )
    except Exception as e:
        return PnRStageResult(
            stage_name="pnr",
            passed=False,
            clock_period_ns=clock_period_ns,
            core_utilization=core_utilization,
            error_message=f"Exception during openroad_pnr: {str(e)}",
        )
    finally:
        if owns_session:
            session.close()
