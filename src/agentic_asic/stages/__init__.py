"""Stages for the agentic-asic multi-stage EDA pipeline."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StageResult:
    stage_name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class ReviewStageResult(StageResult):
    score: int = 100
    violations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SimStageResult(StageResult):
    simulator: str = "icarus"
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    sim_log: str = ""


@dataclass
class SynthStageResult(StageResult):
    target: str = "generic"
    total_cells: int = 0
    cell_counts: Dict[str, int] = field(default_factory=dict)
    inferred_latches: List[str] = field(default_factory=list)
    netlist_file: Optional[str] = None
    spice_file: Optional[str] = None


@dataclass
class PnRStageResult(StageResult):
    wns_ns: float = 0.0
    tns_ns: float = 0.0
    clock_period_ns: float = 2.0
    core_utilization: float = 0.35
    platform: str = "nangate45"
    def_file: Optional[str] = None
    timing_met: bool = True


@dataclass
class FormalStageResult(StageResult):
    verdict: str = "UNKNOWN"
    failed_assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SignoffStageResult(StageResult):
    gds_file: Optional[str] = None
    drc_violations: int = 0
    drc_clean: bool = False
    layout_spice: Optional[str] = None
    lvs_match: Optional[bool] = None


@dataclass
class FpgaStageResult(StageResult):
    board: str = ""
    bitstream_file: Optional[str] = None
    utilization: Dict[str, Any] = field(default_factory=dict)
    fmax_mhz: Optional[float] = None
