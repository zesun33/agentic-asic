# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Signoff reports Sky130 `li.6` LEF-abstract pin hits as informational DRC (`drc_informational`), separate from actionable `drc_violations`.

## [0.2.1] - 2026-09-07

### Added
- Sky130 scale vehicle `fixtures/regfile32x32.v` (+ self-checking TB and complete SDC at 10 ns).
- Sky130 P&R enables detail-route, taps/fillers, PDN, and CTS, with a 90 min tool timeout (no retry on timeout).
- Per-attempt SDC rewrite so CLI / self-heal `clock_period_ns` actually applies (`read_sdc` no longer freezes the period).

### Fixed
- Timing self-heal was a no-op when an SDC file pinned `create_clock -period`.
- Zero-signal-wire / DRT-0073 pin-access failures classified as placement, not timing.
- Timing period bump has a 0.5 ns floor so a 40 ps miss does not burn a second full detailed-route.

## [0.2.0] - 2026-09-06

### Added
- `MCPServerLocator` resolves 8 EDA MCP servers (`gds`, `formal`, `fpga` join the original 5); `asic doctor` verifies all 8.
- Formal stage (`stages/formal.py`): auto-detects `assert` properties in RTL (opt-out via `--no-formal`), proves with `@zesun33/mcp-formal` (`--formal-mode`, `--formal-depth`, `--formal-sources`).
- GDS signoff stage (`stages/signoff.py`): DEF-to-GDS stream-out plus KLayout DRC smoke via `@zesun33/mcp-gds` (opt-out via `--no-signoff`); DRC findings attach as diagnostics.
- Standalone FPGA track (`stages/fpga.py`, `asic fpga run --board`): synth, place-and-route, bitstream packing, and dry-run programming via `@zesun33/mcp-fpga`.
- Signoff JSON schema `1.1.0` with `formal`, `signoff`, and `fpga` stage blocks; dashboard and Markdown report rows for the new stages.

## [0.1.0] - 2026-09-05

### Added
- Initial release of `agentic-asic`, the autonomous silicon compilation and verification orchestrator.
- Multi-stage pipeline integrating `@zesun33/mcp-rtl-review`, `@zesun33/mcp-verilog`, `@zesun33/mcp-cocotb`, `@zesun33/mcp-yosys`, and `@zesun33/mcp-openroad`.
- Closed-loop self-healing heuristics for core utilization and timing slack relaxation.
- Rich terminal dashboard, Markdown tapeout signoff report, and machine-readable JSON signoff schemas.
- Golden verification flow on `fixtures/counter.v` with recorded deterministic transcripts.
- Strict 6-gate verification suite (`scripts/verify.sh`).
