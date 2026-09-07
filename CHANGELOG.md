# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
