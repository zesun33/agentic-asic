"""CLI entrypoint for agentic-asic."""

import argparse
import json
import os
import sys
from typing import List, Optional
from agentic_asic import __version__
from agentic_asic.mcp_client import MCPClientSession, MCPServerLocator
from agentic_asic.pipeline import ASICPipeline
from agentic_asic.reporter import SignoffReporter
from agentic_asic.stages.pnr import run_pnr_stage
from agentic_asic.stages.review import run_review_stage
from agentic_asic.stages.simulate import run_simulate_stage
from agentic_asic.stages.synthesize import run_synthesize_stage


def print_doctor(as_json: bool = False) -> int:
    """Checks the health of all 5 EDA MCP servers and underlying runtime tools."""
    servers = ["review", "verilog", "cocotb", "yosys", "openroad"]
    status: dict = {"version": __version__, "servers": {}}
    all_ok = True

    for s in servers:
        cmd = MCPServerLocator.resolve(s)
        resolved = cmd is not None
        status["servers"][s] = {"resolved": resolved, "command": cmd}
        if not resolved:
            all_ok = False

    if as_json:
        print(json.dumps(status, indent=2))
        return 0 if all_ok else 1

    print("\n\033[1;36m=== agentic-asic Doctor: MCP Toolchain Verification ===\033[0m")
    print(f"  agentic-asic version: {__version__}")
    print("  -------------------------------------------------------------")
    for s, info in status["servers"].items():
        if info["resolved"]:
            print(f"  \033[1;32m✓\033[0m \033[1m{s:<10}\033[0m : {info['command'][1]}")
        else:
            print(f"  \033[1;31m✗\033[0m \033[1m{s:<10}\033[0m : NOT FOUND (Check sibling repos or MCP_*_PATH)")
    print("  -------------------------------------------------------------")
    if all_ok:
        print("  \033[1;32mAll 5 EDA MCP servers are operational and resolved.\033[0m\n")
        return 0
    else:
        print("  \033[1;31mOne or more MCP servers could not be located.\033[0m\n")
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    sources = args.sources
    top = args.top
    if not top:
        # Default top module to base name of first file
        top = os.path.splitext(os.path.basename(sources[0]))[0]

    pipeline = ASICPipeline(
        work_dir=args.work_dir or os.getcwd(),
        clock_period_ns=args.period,
        core_utilization=args.util,
        target_pdk=args.target,
    )

    out = pipeline.run(
        verilog_sources=sources,
        top_module=top,
        testbench=args.tb,
        sdc_file=args.sdc,
        do_pnr=not args.no_pnr,
    )

    results = out["results"]
    duration = out["duration_seconds"]
    retries = out["retries"]

    if args.json:
        report = SignoffReporter.generate_json_report(top, results, duration, retries)
        print(json.dumps(report, indent=2))
    else:
        SignoffReporter.print_terminal_dashboard(top, results, duration, retries)

    if args.report_out:
        md = SignoffReporter.generate_markdown_report(top, results, duration, retries)
        with open(args.report_out, "w") as f:
            f.write(md)
        if not args.json:
            print(f"Wrote signoff markdown report to: {args.report_out}")

    return 0 if out["success"] else 1


def cmd_demo(args: argparse.Namespace) -> int:
    """Executes golden end-to-end demo flow on fixtures/counter.v."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    fixtures_dir = os.path.join(repo_root, "fixtures")

    counter_v = os.path.join(fixtures_dir, "counter.v")
    counter_tb = os.path.join(fixtures_dir, "counter_tb.v")
    counter_sdc = os.path.join(fixtures_dir, "counter.sdc")

    if not os.path.exists(counter_v):
        print(f"Demo fixture not found: {counter_v}", file=sys.stderr)
        return 1

    work_dir = args.work_dir or os.path.join(repo_root, "transcripts", "demo_run")
    os.makedirs(work_dir, exist_ok=True)

    print(f"\n\033[1;36m>>> Running agentic-asic Golden Tapeout Flow on {counter_v} <<<\033[0m")
    pipeline = ASICPipeline(
        work_dir=work_dir,
        clock_period_ns=2.0,
        core_utilization=0.35,
        target_pdk="generic",
    )

    out = pipeline.run(
        verilog_sources=[counter_v],
        top_module="counter",
        testbench=counter_tb,
        sdc_file=counter_sdc,
        do_pnr=True,
    )

    results = out["results"]
    duration = out["duration_seconds"]
    retries = out["retries"]

    SignoffReporter.print_terminal_dashboard("counter", results, duration, retries)

    # Save golden reports
    report_json_path = os.path.join(repo_root, "transcripts", "golden_asic_flow.json")
    report_md_path = os.path.join(repo_root, "transcripts", "golden_tapeout_report.md")

    json_data = SignoffReporter.generate_json_report("counter", results, duration, retries)
    with open(report_json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    md_data = SignoffReporter.generate_markdown_report("counter", results, duration, retries)
    with open(report_md_path, "w") as f:
        f.write(md_data)

    print(f"Generated golden transcript : {report_json_path}")
    print(f"Generated golden report     : {report_md_path}\n")
    return 0 if out["success"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asic",
        description="agentic-asic: Autonomous Silicon Compilation & Verification Orchestrator",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Check EDA MCP server connections")
    p_doc.add_argument("--json", action="store_true", help="Emit JSON output")

    # demo
    p_demo = subparsers.add_parser("demo", help="Run golden end-to-end demo on fixtures/counter.v")
    p_demo.add_argument("--work-dir", type=str, help="Output directory for generated netlists and defs")

    # run
    p_run = subparsers.add_parser("run", help="Run full closed-loop ASIC flow on RTL design")
    p_run.add_argument("sources", nargs="+", help="Verilog source files")
    p_run.add_argument("--top", type=str, help="Top module name (defaults to file basename)")
    p_run.add_argument("--tb", type=str, help="Testbench file (.v or .py for cocotb)")
    p_run.add_argument("--sdc", type=str, help="SDC timing constraints file")
    p_run.add_argument("--period", type=float, default=2.0, help="Target clock period in ns (default: 2.0)")
    p_run.add_argument("--util", type=float, default=0.35, help="Core placement utilization (default: 0.35)")
    p_run.add_argument("--target", type=str, default="nangate45", choices=["generic", "ice40", "sky130", "nangate45"], help="PDK target (default: nangate45)")
    p_run.add_argument("--no-pnr", action="store_true", help="Skip physical design stage")
    p_run.add_argument("--json", action="store_true", help="Emit JSON signoff report to stdout")
    p_run.add_argument("--report-out", type=str, help="Export markdown signoff report to file")
    p_run.add_argument("--work-dir", type=str, help="Working directory for artifacts")

    args = parser.parse_args(argv)

    if args.subcommand == "doctor":
        return print_doctor(as_json=args.json)
    elif args.subcommand == "demo":
        return cmd_demo(args)
    elif args.subcommand == "run":
        return cmd_run(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
