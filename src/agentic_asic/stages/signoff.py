"""Stage 6 (v0.3): GDSII stream-out + DRC + optional extract/LVS via @zesun33/mcp-gds.

Passes iff stream-out succeeds. DRC findings attach as diagnostics/warnings:
the generic geometry deck on abstract stream-out cannot be signoff-grade,
so violations never fail this stage. Pass pdk="sky130A" (pipeline does this
automatically for --target sky130) to run the foundry DRC deck instead --
only meaningful for Sky130 layouts; never auto-detected, since a foundry
deck on a foreign-technology layout reports bogus violations.

When netlist_file AND pdk are given, the stage additionally extracts the
layout netlist (Magic, PDK tech) and LVS-compares it against synthesis
(Netgen). LVS outcome attaches as lvs_match + diagnostics; mismatch does
not fail the stage yet. Without a PDK, extraction is skipped honestly:
generic-tech Magic cannot read GDS-II (no cifinput section).
"""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import SignoffStageResult


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


def run_signoff_stage(
    def_file: str,
    top_module: str,
    gds_file: Optional[str] = None,
    netlist_file: Optional[str] = None,
    pdk: Optional[str] = None,
    timeout_ms: int = 1800000,
    cwd: Optional[str] = None,
    session: Optional[MCPClientSession] = None,
) -> SignoffStageResult:
    """Streams DEF to GDSII, runs DRC, and optionally extract+LVS."""
    norm_def = _relpath_if_possible(def_file, cwd)
    norm_netlist = _relpath_if_possible(netlist_file, cwd) if netlist_file else None

    owns_session = False
    if session is None:
        cmd = MCPServerLocator.resolve("gds")
        if not cmd:
            return SignoffStageResult(
                stage_name="signoff",
                passed=False,
                error_message="Could not resolve @zesun33/mcp-gds executable",
            )
        session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        stream_args: Dict[str, Any] = {"def_file": norm_def, "timeout_ms": timeout_ms}
        if gds_file:
            stream_args["gds_file"] = gds_file
        if pdk:
            # PDK LEFs resolve foreign-technology macros (Sky130 DEFs fail
            # against the default Nangate45 LEFs with "Macro not found").
            stream_args["pdk"] = pdk
        if cwd:
            stream_args["cwd"] = cwd
        stream = session.call_tool("gds_stream_out", stream_args)
        if not isinstance(stream, dict) or not stream.get("success"):
            errs = stream.get("errors", ["stream-out failed"]) if isinstance(stream, dict) else [f"Invalid response: {stream}"]
            return SignoffStageResult(
                stage_name="signoff",
                passed=False,
                error_message=f"GDS stream-out failed: {errs}",
            )

        out_gds = str(stream.get("gdsFile", ""))
        drc_args: Dict[str, Any] = {"gds_file": out_gds, "timeout_ms": timeout_ms}
        if pdk:
            drc_args["pdk"] = pdk
        if cwd:
            drc_args["cwd"] = cwd
        drc = session.call_tool("drc_klayout", drc_args)
        if not isinstance(drc, dict):
            return SignoffStageResult(
                stage_name="signoff",
                passed=False,
                gds_file=out_gds,
                error_message=f"Invalid response from drc_klayout: {drc}",
            )

        violations = drc.get("violations", []) if isinstance(drc.get("violations"), list) else []
        total = int(drc.get("totalViolations", len(violations)))
        clean = bool(drc.get("clean", total == 0))
        diagnostics = [
            f"{v.get('rule', '?')}: {v.get('count', 0)} finding(s)"
            for v in violations
            if isinstance(v, dict)
        ]

        # Optional extract + LVS: layout netlist vs synthesis netlist.
        # PDK-gated: Magic's generic technology cannot read GDS-II at all
        # ("Nothing in cifinput section"), and DEF input needs LEF cell
        # definitions, so extraction is only meaningful with a PDK tech.
        lvs_details: Dict[str, Any] = {}
        lvs_fields: Dict[str, Any] = {}
        if norm_netlist and not pdk:
            diagnostics.append(
                "LVS skipped: GDS extraction needs a PDK technology "
                "(run --target sky130 with a PDK once Sky130 P&R lands)."
            )
        if norm_netlist and pdk:
            layout_spice = f"{top_module}_layout.spice"
            ext_args: Dict[str, Any] = {
                "source": out_gds,
                "cell": top_module,
                "output_spice": layout_spice,
                "timeout_ms": timeout_ms,
            }
            if cwd:
                ext_args["cwd"] = cwd
            ext = session.call_tool("extract_magic", ext_args)
            lvs_details["extract"] = ext
            if isinstance(ext, dict) and ext.get("success"):
                layout_cell = top_module
                lvs_args: Dict[str, Any] = {
                    "schematic_netlist": norm_netlist,
                    "schematic_cell": top_module,
                    "layout_netlist": layout_spice,
                    "layout_cell": layout_cell,
                    "timeout_ms": timeout_ms,
                }
                if pdk:
                    lvs_args["pdk"] = pdk
                if cwd:
                    lvs_args["cwd"] = cwd
                lvs = session.call_tool("lvs_netgen", lvs_args)
                lvs_details["lvs"] = lvs
                if isinstance(lvs, dict):
                    match = lvs.get("match")
                    lvs_fields["layout_spice"] = layout_spice
                    lvs_fields["lvs_match"] = bool(match) if match is not None else None
                    diagnostics.append(
                        f"LVS vs synthesis: {'MATCH' if match else 'MISMATCH'}"
                    )
                else:
                    diagnostics.append(f"LVS returned invalid response: {lvs}")
            else:
                errs = ext.get("errors", ["extraction failed"]) if isinstance(ext, dict) else [f"Invalid response: {ext}"]
                diagnostics.append(f"Layout extraction failed, LVS skipped: {errs}")

        return SignoffStageResult(
            stage_name="signoff",
            passed=True,
            gds_file=out_gds,
            drc_violations=total,
            drc_clean=clean,
            diagnostics=diagnostics,
            details={"stream": stream, "drc": drc, **lvs_details},
            **lvs_fields,
        )
    except Exception as e:
        return SignoffStageResult(
            stage_name="signoff",
            passed=False,
            error_message=f"Exception during signoff: {str(e)}",
        )
    finally:
        if owns_session:
            session.close()
