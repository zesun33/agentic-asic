"""Central ASIC pipeline coordinator orchestrating the 5 EDA MCP stages."""

import os
import shutil
import time
from typing import Any, Dict, List, Optional
from agentic_asic.reporter import SignoffReporter
from agentic_asic.self_healing import SelfHealingEngine
from agentic_asic.stages import (
    PnRStageResult,
    ReviewStageResult,
    SimStageResult,
    StageResult,
    SynthStageResult,
)
from agentic_asic.stages.pnr import run_pnr_stage
from agentic_asic.stages.review import run_review_stage
from agentic_asic.stages.simulate import run_simulate_stage
from agentic_asic.stages.synthesize import run_synthesize_stage
from agentic_asic.stages.formal import run_formal_stage, detect_assertions
from agentic_asic.stages.signoff import run_signoff_stage


def _stage_file(path: str, target_dir: str) -> str:
    """Ensures a file is staged inside target_dir for container isolation."""
    abs_p = os.path.abspath(path)
    abs_dir = os.path.abspath(target_dir)
    try:
        if os.path.commonpath([abs_p, abs_dir]) == abs_dir:
            return os.path.relpath(abs_p, abs_dir)
    except ValueError:
        pass

    dest = os.path.join(abs_dir, os.path.basename(path))
    if abs_p != dest:
        shutil.copy2(abs_p, dest)
    return os.path.basename(dest)


class ASICPipeline:
    """End-to-end closed-loop ASIC compilation and signoff pipeline."""

    def __init__(
        self,
        work_dir: Optional[str] = None,
        clock_period_ns: float = 2.0,
        core_utilization: float = 0.70,
        target_pdk: str = "nangate45",
        min_review_score: int = 70,
    ):
        self.work_dir = os.path.abspath(work_dir or os.getcwd())
        self.clock_period_ns = clock_period_ns
        self.core_utilization = core_utilization
        self.target_pdk = target_pdk
        self.min_review_score = min_review_score
        os.makedirs(self.work_dir, exist_ok=True)

    def run(
        self,
        verilog_sources: List[str],
        top_module: str,
        testbench: Optional[str] = None,
        sdc_file: Optional[str] = None,
        do_pnr: bool = True,
        max_retries: int = 2,
        do_formal: bool = True,
        formal_sources: Optional[List[str]] = None,
        formal_mode: str = "bmc",
        formal_depth: int = 10,
        formal_defines: Optional[List[str]] = None,
        do_signoff: bool = True,
    ) -> Dict[str, Any]:
        """Executes the complete ASIC flow with automated self-healing."""
        start_time = time.time()
        results: Dict[str, StageResult] = {}
        retries_performed = 0

        # P&R consumes the synth netlist in OpenROAD, whose Verilog frontend
        # rejects operator expressions. Only liberty-mapped targets (e.g.
        # nangate45) produce mappable netlists; generic/ice40/xilinx/intel do
        # not. Fail fast instead of running a vacuous flow.
        # Sky130 synthesizes but P&R is nangate45-only (mcp-openroad has no
        # Sky130 platform yet); fail fast with guidance, not a deep stacktrace.
        if do_pnr and self.target_pdk == "sky130":
            duration = time.time() - start_time
            return {
                "success": False,
                "failing_stage": "config",
                "results": {},
                "duration_seconds": duration,
                "retries": retries_performed,
                "error_message": (
                    "do_pnr with target_pdk='sky130' is not supported yet: mcp-openroad "
                    "only implements the nangate45 platform. Use --target nangate45 for "
                    "P&R, or --target sky130 with --no-pnr for synthesis-only."
                ),
            }
        if do_pnr and self.target_pdk == "generic":
            duration = time.time() - start_time
            return {
                "success": False,
                "failing_stage": "config",
                "results": {},
                "duration_seconds": duration,
                "retries": retries_performed,
                "error_message": (
                    "do_pnr requires a liberty-mapped synthesis target (e.g. target_pdk='nangate45'); "
                    "'generic' netlists keep operator expressions OpenROAD cannot read. "
                    "Use --target nangate45 or --no-pnr."
                ),
            }

        # Stage input files into work_dir so Podman/Docker can access them at /workspace
        staged_sources = [_stage_file(s, self.work_dir) for s in verilog_sources]
        staged_tb = _stage_file(testbench, self.work_dir) if testbench else None
        staged_sdc = _stage_file(sdc_file, self.work_dir) if sdc_file else None

        # Stage 1: Review
        rev_res = run_review_stage(
            verilog_sources=staged_sources,
            top_module=top_module,
            cwd=self.work_dir,
            min_score=self.min_review_score,
        )
        results["review"] = rev_res
        if not rev_res.passed:
            duration = time.time() - start_time
            return {
                "success": False,
                "failing_stage": "review",
                "results": results,
                "duration_seconds": duration,
                "retries": retries_performed,
            }

        # Stage 2: Simulation
        sim_res = run_simulate_stage(
            verilog_sources=staged_sources,
            testbench=staged_tb,
            top_module=f"{top_module}_tb" if staged_tb else top_module,
            cwd=self.work_dir,
        )
        results["simulate"] = sim_res
        if not sim_res.passed:
            duration = time.time() - start_time
            return {
                "success": False,
                "failing_stage": "simulate",
                "results": results,
                "duration_seconds": duration,
                "retries": retries_performed,
            }

        # Stage 3 (opt-in by content): Formal property verification.
        # Runs only when RTL carries assert properties (auto-detected) unless
        # explicitly disabled; explicit formal_sources override detection.
        formal_candidates = formal_sources if formal_sources is not None else staged_sources
        if do_formal and detect_assertions(formal_candidates, self.work_dir):
            formal_res = run_formal_stage(
                verilog_sources=formal_candidates,
                top_module=top_module,
                mode=formal_mode,
                depth=formal_depth,
                defines=formal_defines,
                cwd=self.work_dir,
            )
            results["formal"] = formal_res
            if not formal_res.passed:
                duration = time.time() - start_time
                return {
                    "success": False,
                    "failing_stage": "formal",
                    "results": results,
                    "duration_seconds": duration,
                    "retries": retries_performed,
                }

        # Stage 4: Logic Synthesis
        netlist_out = f"{top_module}_synth.v"
        synth_res = run_synthesize_stage(
            verilog_sources=staged_sources,
            top_module=top_module,
            target=self.target_pdk,
            output_netlist=netlist_out,
            cwd=self.work_dir,
        )
        results["synthesize"] = synth_res
        if not synth_res.passed:
            duration = time.time() - start_time
            return {
                "success": False,
                "failing_stage": "synthesize",
                "results": results,
                "duration_seconds": duration,
                "retries": retries_performed,
            }

        # Stage 5: Physical P&R (Optional)
        if do_pnr:
            actual_netlist = synth_res.netlist_file or netlist_out
            if os.path.isabs(actual_netlist):
                actual_netlist = os.path.relpath(actual_netlist, self.work_dir)
            current_util = self.core_utilization
            current_period = self.clock_period_ns
            pnr_success = False

            for attempt in range(max_retries + 1):
                def_out = f"{top_module}_routed.def"
                pnr_res = run_pnr_stage(
                    netlist_file=actual_netlist,
                    top_module=top_module,
                    clock_period_ns=current_period,
                    core_utilization=current_util,
                    output_def=def_out,
                    sdc_file=staged_sdc,
                    cwd=self.work_dir,
                )
                results["pnr"] = pnr_res

                if pnr_res.passed:
                    pnr_success = True
                    break

                if attempt < max_retries:
                    retries_performed += 1
                    # Self-healing parameter adjustment
                    failure_type = "timing" if pnr_res.wns_ns < 0 else "placement"
                    current_util, current_period, reason = SelfHealingEngine.recommend_pnr_relaxation(
                        core_utilization=current_util,
                        clock_period_ns=current_period,
                        wns_ns=pnr_res.wns_ns,
                        failure_type=failure_type,
                    )

            if not pnr_success:
                duration = time.time() - start_time
                return {
                    "success": False,
                    "failing_stage": "pnr",
                    "results": results,
                    "duration_seconds": duration,
                    "retries": retries_performed,
                }

            # Stage 6 (v0.2): GDSII stream-out + DRC smoke on the routed DEF.
            if do_signoff and pnr_success:
                pnr_def = None
                pnr_stage = results.get("pnr")
                if isinstance(pnr_stage, PnRStageResult):
                    pnr_def = pnr_stage.def_file
                if pnr_def:
                    signoff_res = run_signoff_stage(
                        def_file=pnr_def,
                        top_module=top_module,
                        netlist_file=actual_netlist,
                        # Foundry DRC deck only for Sky130 layouts; a PDK
                        # deck on a foreign-technology layout reports bogus
                        # violations, so this is explicit, never auto-detected.
                        pdk="sky130A" if self.target_pdk == "sky130" else None,
                        cwd=self.work_dir,
                    )
                    results["signoff"] = signoff_res
                    if not signoff_res.passed:
                        duration = time.time() - start_time
                        return {
                            "success": False,
                            "failing_stage": "signoff",
                            "results": results,
                            "duration_seconds": duration,
                            "retries": retries_performed,
                        }

        duration = time.time() - start_time
        return {
            "success": True,
            "failing_stage": None,
            "results": results,
            "duration_seconds": duration,
            "retries": retries_performed,
        }
