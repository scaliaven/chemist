# Amber Reference (v1.3 — GAFF2 small-molecule MD)

v1.3 ships a **frozen** GAFF2 + AM1-BCC small-molecule explicit-solvent
MD carve-out via `scripts/parameterize_gaff2.py` + `scripts/run_amber.py`.
For deeper Amber work — REMD, MMPBSA, restart-and-extend, implicit
solvent, biopolymer force fields, cpptraj-driven analysis — use the
sibling **`amber-chemist`** skill, which owns the canonical Amber
surface. Bug fixes that apply to both should land in `amber-chemist`
first; only port back here if the carve-out is still desired.

## §1 — Architectural carve-out

Amber is **the only engine in `ase-chemist` that does not run through
ASE.** Every other backend (EMT, LJ, TIP3P, tblite/xTB, MACE) is wrapped
as an ASE `Calculator` and driven in-process; Amber shells out to
AmberTools binaries (`antechamber`, `parmchk2`, `tleap`) and Amber MD
engines (`pmemd.cuda` / `pmemd` / `sander`) via `subprocess.run`. The MD
integration loop runs natively in pmemd, not in ASE.

The carve-out was a **performance choice, not forced.** ASE ships
`ase.calculators.amber.SANDER` (pysander Python bindings, in-process,
ASE-coherent — drives `Langevin` / `VelocityVerlet` cleanly). v1.3
declined it because pysander binds to CPU sander only, ~10–50× slower
than pmemd.cuda on production systems. Four open options are tracked
in [`PLAN.md`](../../PLAN.md) §"Phase 3": keep pmemd shell-out, switch
to SANDER+ASE, remove Amber entirely, or build a proper ASE Calculator
around pmemd / pmemd.cuda. With `amber-chemist` now shipping as a
sibling skill, there is a documented fifth option: keep this carve-out
as-is and route Amber-deep prompts to `amber-chemist`. v1.0 of
`amber-chemist` took option 5.

## §2 — When to use GAFF2 vs xTB vs the sibling skill

Apply in order; first rule that fits is the answer.

1. **Small organic (≤ ~150 atoms), explicit-solvent MD ≥ 100 ps** →
   GAFF2 + AM1-BCC via the v1.3 scripts. xTB MD past ~1k atoms (any
   solvated drug-sized system) is impractical.
2. **Small organic, quick SP or vacuum optimization** → GFN2-xTB
   (`single_point.py` / `optimize.py`). No parameterization step.
3. **Small organic, short implicit / vacuum thermalization (≤ 50 ps)**
   → GFN2-xTB MD (`run_md.py`).
4. **Protein, nucleic acid, peptide, lipid, complex** → **not in
   `ase-chemist`.** Route to `amber-chemist` (ff19SB+OPC / OL21 ships
   in v1.1). BYO-prmtop runs with `run_amber.py` work today but
   `mdin` defaults are GAFF2-tuned — flag the mismatch.
5. **REMD, MMPBSA, free energy, restart-and-extend, implicit-GB MD,
   alanine scan, per-residue decomposition, QM/MM** → **route to
   `amber-chemist`.** v1.3 ships plain NPT only.

## §3 — Pipeline

```bash
python scripts/parameterize_gaff2.py --structure ligand.pdb \
    --net-charge 0 --water tip3p --buffer 12.0 \
    --output-prefix ligand --output-dir run/

python scripts/run_amber.py --prmtop run/ligand.prmtop \
    --rst run/ligand.rst7 --protocol standard --output-dir run/

python scripts/analyze_traj.py --trajectory run/prod.nc \
    --topology run/ligand.prmtop ...
```

`parameterize_gaff2.py` is idempotent; `run_amber.py` is not — use a
fresh `--output-dir` per run. For richer prep (salt concentration,
SPCE / TIP4P-Ew water, octahedral box, implicit-solvent prep), use
`amber-chemist/scripts/amber_prep.py`.

## §4 — Force fields, water, charges, engines

- **Force field:** GAFF2 only (v1.3 default). `--force-field {ff19SB,
  OL21}` is not exposed; biopolymer prep lives in `amber-chemist`.
  Original GAFF stays usable for literature reproduction by editing
  the tleap deck (`-at gaff`).
- **Water:** TIP3P (default, GAFF2's calibration target) or OPC
  (`--water opc`). TIP4P-Ew / SPC/E are supported by tleap but not
  via the v1.3 CLI — for those, use `amber-chemist/scripts/amber_prep.py`.
- **Charges:** AM1-BCC via `antechamber -c bcc`. **`--net-charge`
  is mandatory** — antechamber silently uses 0 if you don't pass it,
  which shifts every partial charge for any non-neutral species.
  Always confirm the formal charge with the user. RESP via Gaussian
  is more accurate but multi-step; out of scope for v1.3.
- **Engine auto-pick:** `pmemd.cuda > pmemd > sander`, first one on
  PATH. AmberTools25 ships pmemd.cuda open-source. **No GPU-presence
  probe** — if `pmemd.cuda` is on PATH but no GPU is available, pass
  `--engine pmemd` explicitly or the job fails at CUDA init.

## §5 — Known failure modes

- **antechamber atom-type errors** (`could not find atom type` in
  tleap.log): unusual valence states (carbenes, nitrenes, radicals,
  hypervalent atoms). Pre-clean with OpenBabel or run antechamber
  manually from a known-good mol2.
- **Heat stage produces NaN:** almost always wrong `--net-charge`, or
  someone removed `ntc=2, ntf=2` from the mdin. Less commonly a bad
  starting structure with overlapping atoms — minimize longer.
- **Box too small** for anisotropic molecules → re-parameterize with
  `--buffer 15.0`.
- **Density drifts away from 1 g/cm³** past ~200 ps → buffer too small
  or temperature too high.
- **Energy drift in production** → check `cut=10.0` in the mdin; 8 Å
  is too tight for charged species.
- **`pmemd.cuda` OOM** around 100–200k atoms on a 40 GB GPU → reduce
  buffer or split into shorter runs.
- **Truncated octahedron:** v1.3 uses rectangular boxes
  (`solvateBox`). For rotationally symmetric molecules an octahedron
  saves 20–30% of solvent atoms — use `amber-chemist/scripts/amber_prep.py
  --box-shape oct` or edit the tleap deck by hand.

For broader failure-mode catalog (REMD ladders, MMPBSA decks,
implicit-GB choice, demux artifacts), see
`amber-chemist/references/failure_modes.md`.

## What's out of scope (v1.3)

REMD, MMPBSA, free energy (TI/FEP/MBAR), enhanced sampling (aMD, SMD,
umbrella, metadynamics), QM/MM, constant-pH, anisotropic barostat,
SLURM submission, protein/NA force fields, multi-GPU pmemd.cuda,
PLUMED. All of these are honestly deferred — route to `amber-chemist`
(or its [`extension_map.md`](../../amber-chemist/references/extension_map.md))
for everything except SLURM and free energy, which are out of scope
for both skills today.
