"""Stage 5 (opt-in): Formal property verification via @zesun33/mcp-formal."""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import FormalStageResult


def detect_assertions(staged_sources: List[str], work_dir: str) -> bool:
    """Heuristic: run formal only when RTL contains assert properties."""
    import re

    for src in staged_sources:
        p = src if os.path.isabs(src) else os.path.join(work_dir, src)
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        code = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        code = re.sub(r"//[^\n]*", " ", code)
        # Immediate `assert (...)` / concurrent `assert property (...)`;
        # the leading class excludes SVA system tasks ($assertkill, ...).
        if re.search(r"(?<![\w$])assert\s*(?:property\s*)?\(", code):
            return True
    return False


def run_formal_stage(
    verilog_sources: List[str],
    top_module: str,
    mode: str = "bmc",
    depth: int = 10,
    defines: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    session: Optional[MCPClientSession] = None,
) -> FormalStageResult:
    """Proves embedded SVA properties with SymbiYosys (smtbmc+z3)."""
    owns_session = False
    if session is None:
        cmd = MCPServerLocator.resolve("formal")
        if not cmd:
            return FormalStageResult(
                stage_name="formal",
                passed=False,
                verdict="ERROR",
                error_message="Could not resolve @zesun33/mcp-formal executable",
            )
        session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        args: Dict[str, Any] = {
            "verilog_sources": verilog_sources,
            "top_module": top_module,
            "mode": mode,
            "depth": depth,
            # Solver-only constructs (SVA) live behind `ifdef FORMAL because
            # iverilog cannot parse them; define it for every prove run.
            "defines": defines if defines is not None else ["FORMAL"],
        }
        if cwd:
            args["cwd"] = cwd

        res = session.call_tool("formal_prove", args)
        if not isinstance(res, dict):
            return FormalStageResult(
                stage_name="formal",
                passed=False,
                verdict="ERROR",
                error_message=f"Invalid response from formal_prove: {res}",
            )

        verdict = str(res.get("verdict", "UNKNOWN"))
        failed = res.get("failedAssertions", []) or []
        diagnostics = []
        for fa in failed:
            name = fa.get("name", "?") if isinstance(fa, dict) else str(fa)
            loc = fa.get("location", "?") if isinstance(fa, dict) else "?"
            step = fa.get("step", "?") if isinstance(fa, dict) else "?"
            diagnostics.append(f"Counterexample: {name} at {loc} (step {step})")

        passed = verdict == "PROVEN"
        return FormalStageResult(
            stage_name="formal",
            passed=passed,
            verdict=verdict,
            failed_assertions=failed if isinstance(failed, list) else [],
            diagnostics=diagnostics,
            details=res if isinstance(res, dict) else {},
            error_message=None if passed else f"Formal verdict {verdict} (need PROVEN)",
        )
    except Exception as e:
        return FormalStageResult(
            stage_name="formal",
            passed=False,
            verdict="ERROR",
            error_message=f"Exception during formal_prove: {str(e)}",
        )
    finally:
        if owns_session:
            session.close()
