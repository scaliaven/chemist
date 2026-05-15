#!/usr/bin/env bash
# Runs triggering tests as separate Claude Code sessions.
# Each prompt runs in a fresh `claude -p` invocation — clean context per run.
# Per-run timeout prevents one stuck session from blocking the batch.
set -uo pipefail

OUT=results
mkdir -p "$OUT"

# Non-gating environment summary; helps interpret skill behavior in logs.
if [ -x "$(command -v python)" ]; then
  python amber-chemist/scripts/check_env.py --summary-only > "$OUT/amber-chemist_env.txt" 2>&1 || true
fi

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
run_one p11_size_cliff   trigger     "I want to run molecular dynamics on a 5000-atom organic system. What's the right approach with the ase-chemist tools? Don't run anything; just walk me through method selection."

# v1.3 — Amber GAFF2 small-molecule MD. Tests the antechamber / GAFF2 /
# explicit-solvent triggers added in SKILL.md description and the new
# Step 1 task-table entry pointing at parameterize_gaff2.py + run_amber.py.
run_one p12_gaff2_named  trigger     "Run 1 ns of explicit-solvent MD on caffeine in TIP3P water using GAFF2. Starting structure: test-inputs/caffeine.xyz, net charge 0. Write the scripts; don't execute."
run_one p13_antechamber  trigger     "Parameterize the molecule in test-inputs/caffeine.xyz with antechamber AM1-BCC charges (net charge 0) and GAFF2. Write the script; don't execute."

# v1.3 borderline — protein MD is deferred to v2.3. Skill should still
# trigger but explain the v1.3 limit honestly (BYO-prmtop with run_amber.py;
# ff19SB+OPC support is v2.3 territory).
run_one p14_protein_md   borderline  "I want to run MD on a protein in explicit solvent. How would you approach it with the ase-chemist tools? Don't run anything."

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

# amber-chemist v1.0 trigger tests. MD core (a1-a4), REMD core (a3, a5, a11),
# add-ons (a6-a9). Borderlines at the bottom: deferred features (a13) and
# missing-MPI (a14) test honest deferral.
run_one a1_md_named         trigger     "Run 5 ns of GAFF2 explicit-solvent MD on test-inputs/caffeine.xyz in TIP3P, NPT at 300 K with the Monte Carlo barostat. Net charge 0. Write the scripts; don't execute."
run_one a2_extend           trigger     "I have prod.rst7, prod.mdout, prod.nc and system.prmtop from a finished 1 ns run. Extend it by another 2 ns. Write the script; don't execute."
run_one a3_remd             trigger     "Run T-REMD on caffeine in TIP3P GAFF2 with 8 replicas spanning 300-400 K, exchanges every 1000 steps, 1 ns per replica. Write the scripts and groupfile; don't execute."
run_one a4_implicit         trigger     "Run 5 ns implicit-solvent MD on caffeine using GB (igb=2) at 300 K. Net charge 0. Write the scripts; don't execute."
run_one a5_demux            trigger     "I have a finished T-REMD run in remd_out/. Demux it into per-temperature trajectories and plot RMSD vs the first frame for each. Don't execute."
run_one a6_mmpbsa           trigger     "I have prod.nc, complex.prmtop, receptor.prmtop, ligand.prmtop. Compute MMPBSA endpoint binding free energy with GB model 2. Write the script; don't execute."
run_one a7_alanine          trigger     "Run an alanine scan on a 5-residue interface using MMPBSA. I have complex/receptor/ligand prmtops and a 100 ns production trajectory. Write the deck; don't execute."
run_one a8_cpptraj          trigger     "Run cpptraj-driven RMSD and RMSF on test-inputs/prod.nc with topology test-inputs/system.prmtop, masks @CA. Write the script; don't execute."
run_one a9_esander          trigger     "Per-frame energy decomposition via cpptraj esander on prod.nc with system.prmtop, every 10 frames. Write the script; don't execute."
run_one a10_ff19sb          trigger     "I want ff19SB+OPC MD on a 100-residue protein. Walk me through the workflow this skill supports. Don't run anything."
run_one a11_remd_ladder     trigger     "I asked for T-REMD spanning 280-500 K with 6 replicas - what's wrong with that ladder? How do I tune it?"
run_one a12_collision       trigger     "Run 1 ns of explicit-solvent MD on caffeine in TIP3P water using GAFF2. Starting structure: test-inputs/caffeine.xyz, net charge 0. Write the scripts; don't execute."
run_one a13_amd_borderline  borderline  "Run accelerated MD (aMD) on this system. Does this skill handle it?"
run_one a14_remd_no_mpi     borderline  "I want to run REMD but I only have non-MPI pmemd.cuda. What can this skill do?"

# Real-world use cases. These prompts pose research questions in the
# motivation-first phrasing a working chemist would actually use — often
# without naming a method, sometimes describing a phenomenon ("is it
# stable", "does it flip", "for my QSAR model"). They test whether the
# skills route a goal to the right tool, pick a sensible method when none
# is named, and disambiguate between siblings when both could plausibly
# answer. Distinct from the trigger-phrase-style p1-a14 above.

# ase-chemist — research goals that should route through ASE/Gaussian/xTB.
run_one r1_conformer_rank   trigger     "For a paper I need relative DFT energies of three conformers of a drug-like molecule. I have them in conf_1.xyz, conf_2.xyz, conf_3.xyz. Recommend a level of theory and write the comparison script; don't execute."
run_one r2_ir_predict       trigger     "Predict the IR spectrum of formic acid (HCOOH) so I can compare with our experimental measurement. Use B3LYP/6-31G(d) with SMD water. Don't execute."
run_one r3_pt_co_ads        trigger     "I want the adsorption energy of CO on a Pt(111) top site for a catalysis project. Use a 3-layer 4x4 slab. Pick an appropriate calculator and write the script; don't execute."
run_one r4_qsar_descriptors trigger     "I'm building a small QSAR model and need dipole moment, HOMO-LUMO gap, and partial charges for caffeine (test-inputs/caffeine.xyz). What's the fastest sensible level? Write the script; don't execute."
run_one r5_solv_dG_smd      trigger     "Compute the solvation free energy of acetone in water via SMD at M06-2X/6-31+G(d,p). Don't execute."

# amber-chemist — research goals that should route through Amber/cpptraj/MMPBSA.
run_one r6_dock_rescore     trigger     "I have 5 docking poses for a kinase inhibitor (pose_1.prmtop through pose_5.prmtop with matching .rst7 files). Rescore them with MMGBSA so I can pick the best binder. Short prod is fine. Don't execute."
run_one r7_hbond_lifetime   trigger     "I want the longest-lived hydrogen bonds between my ligand and water over a 200 ns trajectory in prod.nc with topology system.prmtop. Don't execute."
run_one r8_ligand_stability trigger     "Is this drug stable in its starting conformation over 50 ns in water? I have drug.mol2 (net charge 0) and want to know whether the central dihedral flips. Don't execute."
run_one r9_perres_decomp    trigger     "I want to know which residues at my protein-ligand interface contribute most to binding. I have complex/receptor/ligand prmtops and prod.nc. Don't execute."
run_one r10_radgyr          trigger     "I'd like to track radius of gyration vs time for a flexible drug over a 100 ns prod.nc (topology system.prmtop) to see whether it collapses. Don't execute."

# Cross-skill disambiguation — both skills could plausibly trigger.
# rX1: small-mol explicit-solvent MD lives in BOTH ase-chemist (carve-out)
#      and amber-chemist (canonical). Either response is defensible; the
#      log is for human review of how each skill positions itself.
# rX2: rigorous absolute binding free energy (FEP/TI/MBAR) is out of scope
#      for both v1.x skills. Honest deferral is the right answer; MMPBSA
#      as the available approximation is a reasonable redirect.
run_one rX1_drug_in_water   borderline  "I want to understand how my drug moves around in water over a few nanoseconds. What's the right tool here? Don't execute."
run_one rX2_fep_binding     borderline  "Compute the absolute binding free energy of my ligand to its protein target. Don't execute."

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