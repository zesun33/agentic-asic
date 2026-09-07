"""Standalone FPGA track via @zesun33/mcp-fpga (never part of the ASIC verdict).

Chains synth -> place-and-route -> bitstream on a board preset, then a
dry-run program plan. Real flashing needs board hardware.
"""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import FpgaStageResult


def _stage_file(path: str, target_dir: str) -> str:
    """Copies absolute sources into target_dir; the container only sees cwd."""
    import shutil

    abs_dir = os.path.abspath(target_dir)
    # Already staged (e.g. basename placed by the CLI): use as-is.
    if not os.path.isabs(path) and os.path.isfile(os.path.join(abs_dir, path)):
        return path
    abs_p = os.path.abspath(path)
    try:
        if os.path.commonpath([abs_p, abs_dir]) == abs_dir:
            return os.path.relpath(abs_p, abs_dir)
    except ValueError:
        pass
    os.makedirs(abs_dir, exist_ok=True)
    dest = os.path.join(abs_dir, os.path.basename(path))
    if abs_p != dest:
        shutil.copy2(abs_p, dest)
    return os.path.basename(dest)


def _session_or_fail(server_key: str, pkg: str) -> MCPClientSession:
    cmd = MCPServerLocator.resolve(server_key)
    if not cmd:
        raise RuntimeError(f"Could not resolve {pkg} executable")
    return MCPClientSession(cmd)


def run_fpga_flow(
    verilog_sources: List[str],
    top_module: str,
    board: str = "icebreaker",
    family: Optional[str] = None,
    cwd: Optional[str] = None,
    session: Optional[MCPClientSession] = None,
) -> FpgaStageResult:
    """Runs the full FPGA flow and returns bitstream + utilization metrics."""
    owns_session = False
    if session is None:
        try:
            session = _session_or_fail("fpga", "@zesun33/mcp-fpga")
        except RuntimeError as e:
            return FpgaStageResult(stage_name="fpga", passed=False, board=board, error_message=str(e))
        owns_session = True

    work_dir = os.path.abspath(cwd or os.getcwd())
    staged = [_stage_file(src, work_dir) for src in verilog_sources]

    def call(name: str, args: Dict[str, Any]) -> Any:
        assert session is not None
        payload = dict(args)
        payload["cwd"] = work_dir
        return session.call_tool(name, payload)

    try:
        synth_args: Dict[str, Any] = {"verilog_sources": staged, "top_module": top_module}
        if family:
            synth_args["family"] = family
        synth = call("fpga_synth", synth_args)
        if not isinstance(synth, dict) or not synth.get("success"):
            errs = synth.get("errors", ["synth failed"]) if isinstance(synth, dict) else [str(synth)]
            return FpgaStageResult(stage_name="fpga", passed=False, board=board, error_message=f"FPGA synth failed: {errs}")

        json_netlist = str(synth.get("jsonNetlist", ""))
        pnr_args: Dict[str, Any] = {"json_netlist": json_netlist, "top_module": top_module, "board": board}
        if family:
            pnr_args["family"] = family
        pnr = call("fpga_place_route", pnr_args)
        if not isinstance(pnr, dict) or not pnr.get("success"):
            errs = pnr.get("errors", ["P&R failed"]) if isinstance(pnr, dict) else [str(pnr)]
            return FpgaStageResult(stage_name="fpga", passed=False, board=board, error_message=f"FPGA P&R failed: {errs}")

        routed = str(pnr.get("outputFile", ""))
        bit = call("fpga_bitstream", {"input_file": routed})
        if not isinstance(bit, dict) or not bit.get("success"):
            errs = bit.get("errors", ["packing failed"]) if isinstance(bit, dict) else [str(bit)]
            return FpgaStageResult(stage_name="fpga", passed=False, board=board, error_message=f"Bitstream packing failed: {errs}")

        bitstream = str(bit.get("bitstreamFile", ""))
        prog = call("fpga_program", {"bitstream_file": bitstream, "dry_run": True})

        util = pnr.get("utilization", {}) if isinstance(pnr, dict) else {}
        fmax = pnr.get("fmax", {}) if isinstance(pnr, dict) else {}
        fmax_mhz: Optional[float] = None
        if isinstance(fmax, dict):
            for entry in fmax.values():
                if isinstance(entry, dict) and isinstance(entry.get("achievedMhz"), (int, float)):
                    v = float(entry["achievedMhz"])
                    fmax_mhz = v if fmax_mhz is None else max(fmax_mhz, v)

        prog_note = ""
        if isinstance(prog, dict):
            prog_note = f" Program plan: {prog.get('programmer', 'iceprog')} dry-run (flashed: {prog.get('flashed', False)})."

        return FpgaStageResult(
            stage_name="fpga",
            passed=True,
            board=board,
            bitstream_file=bitstream,
            utilization=util if isinstance(util, dict) else {},
            fmax_mhz=fmax_mhz,
            diagnostics=[f"Bitstream: {bitstream} ({bit.get('bytes', '?')} bytes).{prog_note}"],
            details={"synth": synth, "pnr": pnr, "bitstream": bit, "program": prog},
        )
    except Exception as e:
        return FpgaStageResult(
            stage_name="fpga",
            passed=False,
            board=board,
            error_message=f"Exception during FPGA flow: {str(e)}",
        )
    finally:
        if owns_session and session is not None:
            session.close()
