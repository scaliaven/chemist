# Failure Modes

Consolidated list of known issues across prep, MD, REMD, analysis,
and scoring. Each entry has the symptom, the cause, and the fix.
Superset of the v1.3 small-molecule failures listed in
`ase-chemist/references/amber.md` §5.

## Prep (`amber_prep.py`)

### "tleap reported success but prmtop missing"
**Cause:** antechamber failed silently (most often: wrong `--net-charge`,
or aromatic-perception ambiguity).
**Fix:** re-run with `--keep-intermediates`, inspect `sqm.out` and
`ANTECHAMBER_*.AC` files. Confirm the formal charge from the SMILES /
Lewis structure.

### "antechamber: cannot find atom type"
**Cause:** GAFF2 doesn't have parameters for the element (e.g. metals,
unusual halogens).
**Fix:** check element coverage; GAFF2 covers H/C/N/O/F/Cl/Br/I/P/S only.
For metals, the user needs a different force field (out of v1.0 scope).

### "tleap: missing parameters for atom type X-Y-Z"
**Cause:** `parmchk2` did not find a fallback parameter; the molecule
has an unusual bonded interaction.
**Fix:** inspect the `.frcmod` file; if a row says `ATTN, need revision`,
the user must supply parameters from QM. v1.0 does not generate them.

### "tleap: solvateBox failed"
**Cause:** the molecule is highly elongated and a 12 Å buffer leaves
the box too thin in one dimension; or the molecule is at the box edge.
**Fix:** increase `--buffer` to 14-16 Å, or center the molecule first
(`pdb4amber -i in.pdb -o out.pdb`).

### "Density never settles during equilibration"
**Cause:** the solute is in a void (initial coordinates are far from a
sensible position) or the system has clashes.
**Fix:** during heat, hold the solute with `--restraint-mask '!@H='`
at 10 kcal/mol/Å². Once heated, release for density.

## MD (`amber_md.py`)

### "pmemd.cuda: VOLUME has changed by more than 50%"
**Cause:** the box collapsed (numerical instability) or the timestep is
too large.
**Fix:** confirm `--timestep 0.002` (default); if the prmtop has
sub-2-fs constraints, reduce to 0.001. Investigate the rst7 — likely
NaN coordinates.

### "pmemd.cuda OOM at start of prod"
**Cause:** water box too large for the GPU's memory.
**Fix:** reduce `--buffer` from 14 Å to 10 Å, or switch to pmemd (CPU)
for the equilibration and back to pmemd.cuda for prod.

### "Energies blow up after a few hundred steps"
**Cause:** unstable initial geometry (un-minimized, clashing atoms).
**Fix:** always run `--stage min` first; never skip minimization.
Confirm `min.mdout` ends with `Total wall time` before chaining.

### "Velocities not propagating after --restart"
**Cause:** `--restart` reads the input rst7 with `irest=1, ntx=5`. If
the rst7 was produced by a stage that didn't write velocities (e.g.
minimization), restart fails silently.
**Fix:** chain min → heat with `--restart` is OK (heat with `irest=0`
generates velocities). For density / prod, only restart from rst7s
that have velocities.

### "Total energy drift in NPT"
**Cause:** Berendsen barostat distorts the NPT distribution. Some
drift is expected.
**Fix:** for production NPT averages, switch to `--barostat
monte_carlo`. Berendsen is fine for equilibration only.

### "Implicit-solvent run rejects --barostat"
**Cause:** GB has no PBC, so barostats don't make sense.
**Fix:** when `--implicit-solvent` is set, omit `--barostat` (or
accept that it's silently ignored).

## REMD (`amber_remd.py`)

### "rem.log shows 0% acceptance for all pairs"
**Cause:** ladder gaps too wide, or one replica diverged at start.
**Fix:** narrow the temperature range or add replicas. Inspect
each `replica_NN/prod.mdout` for early NaN or exploded forces.

### "MPI launch fails: 'np mismatch'"
**Cause:** `mpirun -np N` doesn't match `--n-replicas`.
**Fix:** the script auto-sets `-np` to match; check if you're
overriding with a custom `--mpiexec` invocation.

### "Topology mismatch across replicas"
**Cause:** REMD requires identical topology (same prmtop, same box) for
all replicas; mixing solvateBox and solvateOct outputs fails.
**Fix:** all replicas must be launched from the same prmtop. Don't
re-prep per replica.

### "exchange_rate.txt is empty / unparseable"
**Cause:** pmemd's `rem.log` format changed (rare across AmberTools
versions), or the run crashed before any exchanges happened.
**Fix:** inspect `rem.log` manually; if the run completed but the
script can't parse, file an issue with the AmberTools version.

### "--exchange-every 100 warning"
**Cause:** below the recommended ~500-2000 step range; replicas don't
decorrelate between attempts and acceptance is poor.
**Fix:** increase to 1000 (the script's default).

## Analysis (`amber_analyze.py`)

### "RMSD is monotonically increasing"
**Cause:** the system is genuinely drifting (un-equilibrated), or the
reference frame is bad.
**Fix:** use `--reference <equilibrated.rst7>` instead of frame-1
default. Confirm the reference is from a finished density stage.

### "RDF is flat / zero"
**Cause:** masks don't overlap, or `autoimage` was missing and atoms
left the box.
**Fix:** `amber_analyze.py` injects `autoimage` automatically; if
running cpptraj manually, always include it. Test masks
interactively in cpptraj first.

### "esander: no nonbonded params"
**Cause:** prmtop has bad GAFF2 typing.
**Fix:** re-run `amber_prep.py --keep-intermediates`; inspect the
`.mol2` for unrecognized atom types.

### "ensemble fails: topology mismatch"
**Cause:** trying to demux REMD with non-identical replicas.
**Fix:** REMD must use one prmtop for all replicas. Re-launch.

### "matplotlib plot fails"
**Cause:** matplotlib not installed or DISPLAY-required mode.
**Fix:** `pip install matplotlib`. The script already sets
`matplotlib.use("Agg")` for headless operation.

## Scoring (`amber_score.py`)

### "Topology mismatch between -cp and -y"
**Cause:** trajectory is from a different system than `--complex-prmtop`.
**Fix:** confirm the trajectory was produced from the complex prmtop.

### "No frames after stripping"
**Cause:** `--solvated-prmtop` not set when trajectory has waters.
**Fix:** pass `--solvated-prmtop sys.prmtop` so MMPBSA knows what to
strip.

### "MPI hangs"
**Cause:** `MMPBSA.py.MPI` and pmemd MPI flavor mismatch.
**Fix:** source the same Amber environment that built the MPI
variant. `which mpirun` should match the one used during the
AmberTools build.

### "Alanine scanning requires either a mutated receptor or mutated ligand topology file!"
**Cause:** `&alanine_scanning` / `--alanine-scan` was set without a
mutant topology. MMPBSA.py does not auto-mutate — it diffs your
wild-type prmtop against a mutant prmtop in which exactly one residue
is alanine, one mutation per run.
**Fix:** build the mutant (`tleap` / ParmEd / `ante-MMPBSA.py`, one
residue → ALA) and pass it via `-mr`/`-ml`/`-mc`
(`--mutant-receptor-prmtop` / `--mutant-ligand-prmtop`). Scan multiple
residues with one mutant + one run each.

## Environment (`check_env.py`)

### "AMBERHOME unset" warning
**Cause:** binaries are on PATH but the Amber environment isn't fully
sourced.
**Fix:** `source $AMBERHOME/amber.sh` (or the conda activation that
sets it). Some scripts (especially MMPBSA.py) read `$AMBERHOME` at
runtime.

### "[BROKEN] tblite C extension unloadable" (from sibling skill)
**Cause:** not relevant to amber-chemist — that's `ase-chemist`'s
xTB path. amber-chemist does not use tblite.

## When the failure isn't here

Inspect `$prefix.mdout`'s last 50 lines. Amber's mdout is
human-readable; the cause is usually printed verbatim. If the issue
isn't covered here, the Amber Reference Manual §13 ("Troubleshooting
runs") is the authoritative source. See `manual_lookup.md`.
