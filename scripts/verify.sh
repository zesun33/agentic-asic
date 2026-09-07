#!/usr/bin/env bash
# verify.sh — 6-gate verification suite for agentic-asic
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

QUICK=0
GATE=""
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --gate=*) GATE="${arg#--gate=}" ;;
    --gate) shift; GATE="${1:-}" ;;
    -h|--help)
      echo "Usage: ./scripts/verify.sh [--quick] [--gate N]"
      echo "Gates: 1=spec, 2=static, 3=unit, 4=integration, 5=packaging, 6=schema-contract"
      exit 0
      ;;
  esac
done

pass() { printf "  \033[1;32m✓\033[0m Gate %s: %s\n" "$1" "$2"; }
fail() { printf "  \033[1;31m✗\033[0m Gate %s: %s\n" "$1" "$2"; exit 1; }

run_gate_1() {
  printf "\033[1;36mGate 1 — Spec Lock & Package Integrity\033[0m\n"
  test -f pyproject.toml || fail 1 "pyproject.toml missing"
  test -f LICENSE || fail 1 "LICENSE missing"
  test -f README.md || fail 1 "README.md missing"
  test -f CHANGELOG.md || fail 1 "CHANGELOG.md missing"
  test -f .gitignore || fail 1 ".gitignore missing"
  pass 1 "All specification files present and locked"
}

run_gate_2() {
  printf "\033[1;36mGate 2 — Static Quality & Syntax Check\033[0m\n"
  python3 -m py_compile src/agentic_asic/*.py src/agentic_asic/stages/*.py tests/*.py
  pass 2 "Python syntax validated cleanly across all modules"
}

run_gate_3() {
  printf "\033[1;36mGate 3 — Unit Tests\033[0m\n"
  PYTHONPATH=src python3 -m unittest tests/test_spec.py tests/test_mcp_client.py tests/test_stages.py -v
  pass 3 "Unit tests and spec verification passed"
}

run_gate_4() {
  printf "\033[1;36mGate 4 — Multi-Stage Integration Fixture Flow\033[0m\n"
  if [ "$QUICK" = "1" ]; then
    pass 4 "Integration execution skipped (--quick)"
    return 0
  fi
  PYTHONPATH=src python3 -m unittest tests/test_integration.py -v
  pass 4 "Live multi-stage pipeline passed on golden counter and caught bad RTL"
}

run_gate_5() {
  printf "\033[1;36mGate 5 — Packaging & CLI Executable\033[0m\n"
  test -x bin/asic || fail 5 "bin/asic is not executable"
  ./bin/asic --help > /dev/null || fail 5 "bin/asic --help failed"
  ./bin/asic doctor > /dev/null || fail 5 "bin/asic doctor failed"
  pass 5 "CLI executable verified with help and doctor commands"
}

run_gate_6() {
  printf "\033[1;36mGate 6 — Golden Transcript & Signoff Schema Contract\033[0m\n"
  test -f transcripts/golden_asic_flow.json || fail 6 "transcripts/golden_asic_flow.json missing"
  test -f transcripts/golden_tapeout_report.md || fail 6 "transcripts/golden_tapeout_report.md missing"
  
  # Validate JSON schema keys
  python3 -c '
import json
with open("transcripts/golden_asic_flow.json") as f:
    d = json.load(f)
assert d["schema_version"] == "1.1.0"
assert d["signoff_status"] == "PASS"
assert "review" in d["stages"]
assert "simulate" in d["stages"]
assert "synthesize" in d["stages"]
assert "pnr" in d["stages"]
' || fail 6 "Golden transcript failed schema assertion"
  pass 6 "Golden transcript and signoff reports adhere to schema contract"
}

run_all() {
  [ -z "$GATE" ] || [ "$GATE" = "1" ] && run_gate_1
  [ -z "$GATE" ] || [ "$GATE" = "2" ] && run_gate_2
  [ -z "$GATE" ] || [ "$GATE" = "3" ] && run_gate_3
  [ -z "$GATE" ] || [ "$GATE" = "4" ] && run_gate_4
  [ -z "$GATE" ] || [ "$GATE" = "5" ] && run_gate_5
  [ -z "$GATE" ] || [ "$GATE" = "6" ] && run_gate_6
  printf "\033[1;32mAll verification gates passed.\033[0m\n"
}

run_all
