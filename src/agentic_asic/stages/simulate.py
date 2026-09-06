"""Stage 2: Verification & Simulation via @zesun33/mcp-verilog and @zesun33/mcp-cocotb."""

import os
from typing import Any, Dict, List, Optional
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.stages import SimStageResult


def _relpath_if_possible(p: str, start: Optional[str]) -> str:
    if not start:
        return p
    try:
        abs_p = os.path.abspath(p)
        abs_start = os.path.abspath(start)
        if abs_p.startswith(abs_start):
            return os.path.relpath(abs_p, abs_start)
    except Exception:
        pass
    return p


def run_simulate_stage(
    verilog_sources: List[str],
    testbench: Optional[str] = None,
    top_module: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout_ms: int = 15000,
    dump_waves: bool = False,
    cocotb_session: Optional[MCPClientSession] = None,
    verilog_session: Optional[MCPClientSession] = None,
) -> SimStageResult:
    """Simulates RTL using either Icarus Verilog or Cocotb testbenches."""
    norm_sources = [_relpath_if_possible(s, cwd) for s in verilog_sources]
    norm_tb = _relpath_if_possible(testbench, cwd) if testbench else None

    # Check if testbench is Python cocotb test
    is_cocotb = norm_tb is not None and (norm_tb.endswith(".py") or "cocotb" in norm_tb.lower())

    if is_cocotb:
        owns_session = False
        if cocotb_session is None:
            cmd = MCPServerLocator.resolve("cocotb")
            if not cmd:
                return SimStageResult(
                    stage_name="simulate",
                    passed=False,
                    simulator="cocotb",
                    error_message="Could not resolve @zesun33/mcp-cocotb executable",
                )
            cocotb_session = MCPClientSession(cmd, cwd=cwd)
            owns_session = True

        try:
            py_mod = os.path.splitext(os.path.basename(norm_tb))[0]
            args: Dict[str, Any] = {
                "verilog_sources": norm_sources,
                "toplevel": top_module or "counter",
                "python_module": py_mod,
                "timeout_ms": timeout_ms,
            }
            if cwd:
                args["cwd"] = cwd
            res = cocotb_session.call_tool("cocotb_run", args)
            passed = res.get("passed", res.get("success", False)) if isinstance(res, dict) else False
            tests_run = res.get("tests_run", 1) if isinstance(res, dict) else 0
            tests_passed = res.get("tests_passed", 1 if passed else 0) if isinstance(res, dict) else 0
            tests_failed = res.get("tests_failed", 0 if passed else 1) if isinstance(res, dict) else 1

            return SimStageResult(
                stage_name="simulate",
                passed=passed,
                simulator="cocotb",
                tests_run=tests_run,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                sim_log=str(res.get("log", "") if isinstance(res, dict) else res),
                details=res if isinstance(res, dict) else {"raw": res},
                error_message=None if passed else "Cocotb regression tests failed",
            )
        except Exception as e:
            return SimStageResult(
                stage_name="simulate",
                passed=False,
                simulator="cocotb",
                error_message=f"Exception during cocotb simulation: {str(e)}",
            )
        finally:
            if owns_session:
                cocotb_session.close()

    # Standard Verilog testbench or syntax check via mcp-verilog
    owns_session = False
    if verilog_session is None:
        cmd = MCPServerLocator.resolve("verilog")
        if not cmd:
            return SimStageResult(
                stage_name="simulate",
                passed=False,
                simulator="iverilog",
                error_message="Could not resolve @zesun33/mcp-verilog executable",
            )
        verilog_session = MCPClientSession(cmd, cwd=cwd)
        owns_session = True

    try:
        if norm_tb:
            all_files = list(norm_sources)
            if norm_tb not in all_files:
                all_files.append(norm_tb)
            args = {
                "files": all_files,
                "timeout_ms": timeout_ms,
                "dump_waves": dump_waves,
            }
            if top_module:
                args["top_module"] = top_module
            if cwd:
                args["cwd"] = cwd

            res = verilog_session.call_tool("verilog_simulate", args)
            passed = res.get("success", res.get("passed", False)) if isinstance(res, dict) else False
            output_log = res.get("stdout", "") or res.get("output", "") if isinstance(res, dict) else str(res)
            return SimStageResult(
                stage_name="simulate",
                passed=passed,
                simulator="iverilog",
                tests_run=1,
                tests_passed=1 if passed else 0,
                tests_failed=0 if passed else 1,
                sim_log=output_log,
                details=res if isinstance(res, dict) else {"raw": res},
                error_message=None if passed else "Icarus Verilog testbench simulation failed",
            )
        else:
            # Syntax & elaboration check
            args = {
                "files": norm_sources,
                "compiler": "iverilog",
            }
            if top_module:
                args["top_module"] = top_module
            if cwd:
                args["cwd"] = cwd

            res = verilog_session.call_tool("verilog_compile", args)
            passed = res.get("success", res.get("passed", False)) if isinstance(res, dict) else False
            return SimStageResult(
                stage_name="simulate",
                passed=passed,
                simulator="iverilog-compile",
                tests_run=1,
                tests_passed=1 if passed else 0,
                tests_failed=0 if passed else 1,
                sim_log=str(res),
                details=res if isinstance(res, dict) else {"raw": res},
                error_message=None if passed else "Verilog syntax/elaboration compilation check failed",
            )
    except Exception as e:
        return SimStageResult(
            stage_name="simulate",
            passed=False,
            simulator="iverilog",
            error_message=f"Exception during verilog execution: {str(e)}",
        )
    finally:
        if owns_session:
            verilog_session.close()
