"""Stage 3: RTL Synthesis & Latch Triage via @zesun33/mcp-yosys."""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import SynthStageResult


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


def run_synthesize_stage(
    verilog_sources: List[str],
    top_module: str,
    target: str = "generic",
    output_netlist: Optional[str] = None,
    output_spice: Optional[str] = None,
    cwd: Optional[str] = None,
    allow_latches: bool = False,
    session: Optional[MCPClientSession] = None,
) -> SynthStageResult:
    """Synthesizes RTL, triages latches, and produces gate netlist."""
    norm_sources = [_relpath_if_possible(s, cwd) for s in verilog_sources]
    norm_netlist = _relpath_if_possible(output_netlist, cwd) if output_netlist else None
    norm_spice = _relpath_if_possible(output_spice, cwd) if output_spice else None

    owns_session = False
    if session is None:
        cmd = MCPServerLocator.resolve("yosys")
        if not cmd:
            return SynthStageResult(
                stage_name="synthesize",
                passed=False,
                error_message="Could not resolve @zesun33/mcp-yosys executable",
            )
        session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        # 1. First run latch check
        latch_args: Dict[str, Any] = {
            "verilog_sources": norm_sources,
            "top_module": top_module,
        }
        if cwd:
            latch_args["cwd"] = cwd

        latch_res = session.call_tool("yosys_check_latch", latch_args)
        inferred_latches: List[str] = []
        if isinstance(latch_res, dict):
            has_latches = latch_res.get("hasLatches", False) or latch_res.get("has_latches", False)
            raw_latches = latch_res.get("latches") or latch_res.get("inferred_latches") or []
            if isinstance(raw_latches, list):
                for item in raw_latches:
                    if isinstance(item, dict):
                        inferred_latches.append(
                            f"{item.get('module', '')}.{item.get('variable', '')} [Line {item.get('line', '?')}]"
                        )
                    else:
                        inferred_latches.append(str(item))
            if not inferred_latches and has_latches:
                inferred_latches = ["Inferred transparent latch detected"]

        if inferred_latches and not allow_latches:
            return SynthStageResult(
                stage_name="synthesize",
                passed=False,
                target=target,
                inferred_latches=inferred_latches,
                diagnostics=[f"Latch detected: {l}" for l in inferred_latches],
                details={"latch_check": latch_res},
                error_message=f"Synthesis aborted: Inferred {len(inferred_latches)} latch(es) detected: {', '.join(inferred_latches)}",
            )

        # 2. Run synthesis
        synth_args: Dict[str, Any] = {
            "verilog_sources": norm_sources,
            "top_module": top_module,
            "target": target,
        }
        if norm_netlist:
            synth_args["output_netlist"] = norm_netlist
        if cwd:
            synth_args["cwd"] = cwd

        synth_res = session.call_tool("yosys_synthesize", synth_args)
        if not isinstance(synth_res, dict):
            return SynthStageResult(
                stage_name="synthesize",
                passed=False,
                target=target,
                error_message=f"Invalid response from yosys_synthesize: {synth_res}",
            )

        passed = synth_res.get("success", synth_res.get("passed", False))
        cell_counts = synth_res.get("cellsByType") or synth_res.get("cell_counts") or {}
        total_cells = synth_res.get("cellCount") or synth_res.get("total_cells") or sum(cell_counts.values()) if cell_counts else 0
        netlist_path = synth_res.get("netlistPath") or synth_res.get("output_netlist") or output_netlist
        if netlist_path and cwd and not os.path.isabs(netlist_path):
            netlist_path = os.path.join(cwd, netlist_path)

        # 3. Optional SPICE schematic for LVS (Sky130 hierarchical export).
        spice_path: Optional[str] = None
        spice_details: Dict[str, Any] = {}
        if passed and norm_spice and netlist_path:
            spice_args: Dict[str, Any] = {
                "netlist_file": _relpath_if_possible(netlist_path, cwd),
                "top_module": top_module,
                "output_spice": norm_spice,
            }
            if cwd:
                spice_args["cwd"] = cwd
            spice_res = session.call_tool("yosys_write_spice", spice_args)
            spice_details["spice"] = spice_res
            if isinstance(spice_res, dict) and spice_res.get("success"):
                spice_path = spice_res.get("spiceFile") or output_spice
                if spice_path and cwd and not os.path.isabs(spice_path):
                    spice_path = os.path.join(cwd, spice_path)

        return SynthStageResult(
            stage_name="synthesize",
            passed=passed,
            target=target,
            total_cells=total_cells,
            cell_counts=cell_counts,
            inferred_latches=inferred_latches,
            netlist_file=netlist_path,
            spice_file=spice_path,
            details={"synth": synth_res, "latch": latch_res, **spice_details},
            error_message=None if passed else "Yosys synthesis failed to generate netlist",
        )
    except Exception as e:
        return SynthStageResult(
            stage_name="synthesize",
            passed=False,
            target=target,
            error_message=f"Exception during yosys synthesis: {str(e)}",
        )
    finally:
        if owns_session:
            session.close()
