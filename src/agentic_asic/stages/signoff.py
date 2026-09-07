"""Stage 6 (v0.2): GDSII stream-out + DRC smoke via @zesun33/mcp-gds.

Passes iff both tools execute successfully. DRC findings attach as
diagnostics/warnings: the generic geometry deck on abstract stream-out
cannot be signoff-grade, so violations never fail this stage in v0.2.
DRC-clean gating waits on PDK rule decks.
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
    cwd: Optional[str] = None,
    session: Optional[MCPClientSession] = None,
) -> SignoffStageResult:
    """Streams DEF to GDSII and runs KLayout DRC smoke checks."""
    norm_def = _relpath_if_possible(def_file, cwd)

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
        stream = session.call_tool(
            "gds_stream_out",
            {"def_file": norm_def, **({"gds_file": gds_file} if gds_file else {}), **({"cwd": cwd} if cwd else {})},
        )
        if not isinstance(stream, dict) or not stream.get("success"):
            errs = stream.get("errors", ["stream-out failed"]) if isinstance(stream, dict) else [f"Invalid response: {stream}"]
            return SignoffStageResult(
                stage_name="signoff",
                passed=False,
                error_message=f"GDS stream-out failed: {errs}",
            )

        out_gds = str(stream.get("gdsFile", ""))
        drc = session.call_tool(
            "drc_klayout",
            {"gds_file": out_gds, **({"cwd": cwd} if cwd else {})},
        )
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

        return SignoffStageResult(
            stage_name="signoff",
            passed=True,
            gds_file=out_gds,
            drc_violations=total,
            drc_clean=clean,
            diagnostics=diagnostics,
            details={"stream": stream, "drc": drc},
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
