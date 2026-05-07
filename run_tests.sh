#!/usr/bin/env bash
# Runs triggering tests as separate Claude Code sessions.
# Each prompt runs in a fresh `claude -p` invocation — clean context per run.
# Per-run timeout prevents one stuck session from blocking the batch.
set -uo pipefail

OUT=results
mkdir -p "$OUT"

# Per-run wall-clock limit. 180s is enough for Claude to read SKILL.md,
# read 1-2 reference files, and write a code response. It's NOT enough to
# run a real MD simulation, which is what we want — we're testing whether
# the skill produces correct code, not whether the code finishes executing.
TIMEOUT_SECS="${TIMEOUT_SECS:-180}"

# Detect which timeout binary we have. macOS lacks GNU `timeout` by default;
# `gtimeout` is provided by `brew install coreutils`. On Linux, plain `timeout`.
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN=timeout
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN=gtimeout
else
  echo "ERROR: no timeout binary found. On macOS: brew install coreutils" >&2
  exit 1
fi

run_one () {
  local id="$1" expected="$2" prompt="$3"
  local logf="$OUT/${id}.log"
  local statusf="$OUT/${id}.status"

  echo "=== [$id] expected=$expected (timeout=${TIMEOUT_SECS}s) ===" | tee "$logf"
  echo "PROMPT: $prompt" >> "$logf"
  echo "---" >> "$logf"

  local start=$SECONDS
  # --kill-after sends SIGKILL 10s after SIGTERM if the process doesn't exit.
  # claude -p is generally well-behaved on SIGTERM but let's be belt-and-suspenders.
  "$TIMEOUT_BIN" --kill-after=10s "${TIMEOUT_SECS}s" \
    claude -p "$prompt" --verbose --output-format stream-json \
    >> "$logf" 2>&1
  local rc=$?
  local elapsed=$((SECONDS - start))

  # GNU `timeout` exits 124 on timeout, 137 if the kill-after fired.
  case $rc in
    0)        echo "ok"      > "$statusf" ;;
    124|137)  echo "timeout" > "$statusf" ;;
    *)        echo "error:$rc" > "$statusf" ;;
  esac

  echo "  done -> $logf  (rc=$rc, ${elapsed}s, $(cat "$statusf"))"
}

# Format: id | expected | prompt
run_one p1_method_named  trigger     "I have test-inputs/caffeine.xyz. Optimize it with GFN2-xTB and tell me the HOMO-LUMO gap. Don't actually run the simulation — just write the script I would run."
run_one p2_relax_synonym trigger     "Can you relax the structure in test-inputs/cluster.xyz for me? Just need a reasonable minimum, nothing fancy. Write the script; don't execute it."
run_one p3_md_no_method  trigger     "Run 20 ps of NVT dynamics on liquid argon at 90 K. Starting config is in test-inputs/ar108.xyz. Write the script — don't execute the simulation."
run_one p4_analyze_traj  trigger     "I've got a trajectory at test-inputs/md.traj from a previous run. Plot RMSD vs the first frame and check whether energy is drifting. Write the analysis script; don't execute it yet."
run_one p5_build_struct  trigger     "Build a Pt(111) surface, 4 layers, 4x4, with a CO molecule on the top site. Save as POSCAR. Just write the script — don't run it."

# v1.2 — MACE foundation models. Tests the trigger contract added in
# SKILL.md description ("speed up MD with a foundation model", "MACE-OFF",
# "run a 5000-atom system") and the method-selection rule that points
# past the xTB cliff at MACE.
run_one p10_mace_named   trigger     "Run NVT MD on test-inputs/caffeine.xyz at 300 K for 50 ps using MACE-OFF. Write the script; don't execute it."
run_one p11_size_cliff   trigger     "I want to run molecular dynamics on a 5000-atom organic system. What's the right approach with the ase-simulation tools? Don't run anything; just walk me through method selection."

# v1.3 — Amber GAFF2 small-molecule MD. Tests the antechamber / GAFF2 /
# explicit-solvent triggers added in SKILL.md description and the new
# Step 1 task-table entry pointing at parameterize_gaff2.py + run_amber.py.
run_one p12_gaff2_named  trigger     "Run 1 ns of explicit-solvent MD on caffeine in TIP3P water using GAFF2. Starting structure: test-inputs/caffeine.xyz, net charge 0. Write the scripts; don't execute."
run_one p13_antechamber  trigger     "Parameterize the molecule in test-inputs/caffeine.xyz with antechamber AM1-BCC charges (net charge 0) and GAFF2. Write the script; don't execute."

# v1.3 borderline — protein MD is deferred to v2.3. Skill should still
# trigger but explain the v1.3 limit honestly (BYO-prmtop with run_amber.py;
# ff19SB+OPC support is v2.3 territory).
run_one p14_protein_md   borderline  "I want to run MD on a protein in explicit solvent. How would you approach it with the ase-simulation tools? Don't run anything."

# v1.4 — Gaussian DFT (SP / Opt / Freq). Tests the trigger contract for
# DFT-named methods (B3LYP, ωB97X-D, def2-TZVP), the no-defaults policy
# (skill should NOT silently pick method/basis), and the Freq+thermochem
# task entry that points at gaussian_freq.py.
run_one p15_gaussian_sp  trigger     "Compute a DFT single-point on test-inputs/caffeine.xyz at ωB97X-D / def2-TZVP, neutral closed-shell. Write the script; don't execute."
run_one p16_gaussian_freq trigger    "I need Gibbs free energy at 298 K for caffeine at B3LYP-D3/def2-TZVP. Starting structure: test-inputs/caffeine.xyz. Write the optimize-then-freq pipeline; don't execute."

# v1.4 borderline — user asks for DFT without specifying method/basis.
# The no-defaults policy says the skill should refuse silent defaults;
# it should ask or surface a recommendation, not just pick.
run_one p17_dft_no_method borderline "Run a DFT calculation on test-inputs/caffeine.xyz. What's the right approach with this skill?"

run_one p6_general_know  no_trigger  "What's the boiling point of water at 1 atm in Celsius?"
run_one p7_python_only   no_trigger  "Write a Python function that takes a list of dicts and groups them by a key."
run_one p8_definitional  borderline  "Explain the difference between NVT and NPT ensembles."
run_one p9_borderline    borderline  "How does Langevin dynamics work?"

# Quick summary so you know at a glance what to investigate.
echo
echo "=== Summary ==="
for f in "$OUT"/*.status; do
  id=$(basename "$f" .status)
  printf "  %-22s %s\n" "$id" "$(cat "$f")"
done

# Non-zero exit if any run timed out or errored, so CI / re-run loops can detect it.
if grep -qvE '^ok$' "$OUT"/*.status; then
  echo
  echo "Some runs did not complete cleanly. See logs in $OUT/."
  exit 1
fi