"""Stage 1: AST Code Review & Quality Audit via @zesun33/mcp-rtl-review."""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import ReviewStageResult


def run_review_stage(
    verilog_sources: List[str],
    top_module: Optional[str] = None,
    cwd: Optional[str] = None,
    min_score: int = 70,
    ruleset: str = "standard",
    session: Optional[MCPClientSession] = None,
) -> ReviewStageResult:
    """Runs static AST audit on Verilog source files."""
    owns_session = False
    if session is None:
        cmd = MCPServerLocator.resolve("review")
        if not cmd:
            return ReviewStageResult(
                stage_name="review",
                passed=False,
                error_message="Could not resolve @zesun33/mcp-rtl-review executable",
            )
        session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        args: Dict[str, Any] = {
            "verilog_sources": verilog_sources,
            "ruleset": ruleset,
        }
        if top_module:
            args["top_module"] = top_module
        if cwd:
            args["cwd"] = cwd

        res = session.call_tool("rtl_review", args)
        if not isinstance(res, dict):
            return ReviewStageResult(
                stage_name="review",
                passed=False,
                error_message=f"Invalid response from rtl_review: {res}",
            )

        score = res.get("score", 0)
        violations = res.get("violations", [])
        errors_count = res.get("errors", 0)
        
        passed = (score >= min_score) and (errors_count == 0)
        diagnostics = []
        for v in violations:
            rule = v.get("rule", "UNKNOWN")
            msg = v.get("message", "")
            line = v.get("line", "?")
            diagnostics.append(f"[Line {line}] {rule}: {msg}")

        return ReviewStageResult(
            stage_name="review",
            passed=passed,
            score=score,
            violations=violations,
            diagnostics=diagnostics,
            details=res,
            error_message=None if passed else f"Review score {score}/100 below threshold {min_score} or has {errors_count} critical error(s)",
        )
    except Exception as e:
        return ReviewStageResult(
            stage_name="review",
            passed=False,
            error_message=f"Exception during rtl_review: {str(e)}",
        )
    finally:
        if owns_session:
            session.close()
