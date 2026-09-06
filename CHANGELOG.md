# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-05

### Added
- Initial release of `agentic-asic`, the autonomous silicon compilation and verification orchestrator.
- Multi-stage pipeline integrating `@zesun33/mcp-rtl-review`, `@zesun33/mcp-verilog`, `@zesun33/mcp-cocotb`, `@zesun33/mcp-yosys`, and `@zesun33/mcp-openroad`.
- Closed-loop self-healing heuristics for core utilization and timing slack relaxation.
- Rich terminal dashboard, Markdown tapeout signoff report, and machine-readable JSON signoff schemas.
- Golden verification flow on `fixtures/counter.v` with recorded deterministic transcripts.
- Strict 6-gate verification suite (`scripts/verify.sh`).
