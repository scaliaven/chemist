# Amber Reference (v1.3 — GAFF2 small-molecule MD)

This file replaces the v2 stub for the **GAFF2 small-molecule path**.
v1.3 ships:

- `scripts/parameterize_gaff2.py` — antechamber AM1-BCC charges →
  parmchk2 frcmod → tleap solvation in TIP3P / OPC → `.prmtop` /
  `.rst7`.
- `scripts/run_amber.py` — Jinja-style mdin templates for
  `min` / `heat` / `density` / `prod`, engine selection
  (`pmemd.cuda` > `pmemd` > `sander`), NetCDF `.nc` output handed to
  `analyze_traj.py`.

**Protein and nucleic-acid MD** (ff19SB+OPC, OL21) are deferred to
**v2.3** — the prep pipeline (pdb4amber, multi-residue tleap recipes,
disulfide handling, capping) is its own design problem and the v1.3
scripts deliberately do not adapt for it.

## §1. Method-selection rules

Apply in order. The first rule that fits is your answer.

1. **System is a single small organic molecule (≤ ~150 atoms) and the
   user wants explicit-solvent MD** → GAFF2 + AM1-BCC, run via the
   v1.3 scripts. Why: classical force fields scale; GFN2-xTB does not
   past ~1k atoms (and explicit solvation pushes any drug-sized solute
   well past that with a 12 Å buffer).
2. **System is a small organic molecule and the user wants a quick
   energy / single-point / vacuum optimization** → GFN2-xTB. Why: no
   parameterization step, no charge-and-multiplicity-and-solvent
   ceremony. Use `scripts/single_point.py --calculator xtb` or
   `scripts/optimize.py --calculator xtb`.
3. **System is a small organic in implicit solvent or vacuum that the
   user wants to thermalize** → GFN2-xTB MD via `scripts/run_md.py`.
   Why: for short runs (≤ 50 ps) on small molecules, xTB is honest and
   doesn't need parameterization.
4. **System is a protein, nucleic acid, peptide, lipid, or any
   biopolymer** → not yet supported. v2.3 will add ff19SB+OPC and
   OL21 paths. Today: tell the user honestly that v1.3 is GAFF2 only;
   they can run their existing tleap workflow outside the skill and
   feed the resulting `.prmtop` / `.rst7` to `run_amber.py` with
   `--engine pmemd` (the script does not check what force field is
   in the prmtop). Caveat them that v1.3's `mdin` defaults are tuned
   for GAFF2 small molecules — protein production runs may want
   different `cut`, `gamma_ln`, restraints, etc.
5. **System needs free energy, REMD, QM/MM, umbrella sampling,
   constant-pH, or any enhanced-sampling protocol** → not in scope
   for v1.3 or v2.x. These are research workflows with their own
   design pass. Tell the user honestly.

## §2. Pipeline

The two-script pipeline is:

```bash
# Step 1: parameterize. Output: <prefix>.prmtop, <prefix>.rst7.
python scripts/parameterize_gaff2.py \
    --structure ligand.pdb \
    --net-charge 0 \
    --water tip3p \
    --buffer 12.0 \
    --output-prefix ligand --output-dir run/

# Step 2: run MD. Output: run/min.{nc,rst7,mdout}, run/heat.{...},
# run/density.{...}, run/prod.{...}.
python scripts/run_amber.py \
    --prmtop run/ligand.prmtop --rst run/ligand.rst7 \
    --protocol standard --output-dir run/

# Step 3: analyze the production trajectory.
python scripts/analyze_traj.py --trajectory run/prod.nc \
    --topology run/ligand.prmtop ...
```

`parameterize_gaff2.py` is idempotent — re-running it overwrites the
`.prmtop`/`.rst7` and intermediates. `run_amber.py` is **not**
idempotent: re-running with the same `--output-dir` overwrites the
`mdout` files but does not delete old `.nc` trajectories from
previous runs. Use a fresh `--output-dir` per run.

## §3. Force fields and water models

### Force fields

- **GAFF2** is the default and the only thing v1.3 supports for small
  molecules. It's the post-2020 successor to GAFF, calibrated on a
  larger ZINC-derived dataset, with revised dihedral parameters that
  produce more reliable conformer ensembles.
- **GAFF (the original)** stays usable if the user is reproducing
  literature that explicitly used it. Pass `-at gaff` to antechamber
  manually; v1.3's `parameterize_gaff2.py` does not expose the flag
  (intentional — not the documented default in 2026).
- **GAFF2 + RESP** is more accurate for charged species but needs an
  explicit Gaussian or psi4 single-point. Out of scope for v1.3;
  AM1-BCC is good enough for ~98% of the GAFF2 calibration set.

### Water models

- **TIP3P** is GAFF2's calibration target — pair them. This is the
  v1.3 default.
- **OPC** is a more accurate 4-site water model; pairs naturally with
  ff19SB (proteins) but is fine with GAFF2 too. Pass `--water opc` if
  the user explicitly wants OPC; otherwise stay on TIP3P.
- **TIP4P-Ew, SPC/E, etc.** — supported by tleap but not exposed by
  the v1.3 CLI. Edit `tleap.in` by hand if you need one of these and
  re-run `tleap` directly; the rest of `run_amber.py` will work.

### Charge assignment

- **AM1-BCC via `antechamber -c bcc`** is the v1.3 default. Fast
  (semi-empirical), well-calibrated for GAFF2.
- **RESP via Gaussian + RED-Server** is more accurate but multi-step,
  license-gated (Gaussian), and does not belong in a one-shot CLI.
  Out of scope for v1.3.
- **The `--net-charge` flag is mandatory** — antechamber silently
  uses 0 if you don't pass it, which gives wrong AM1-BCC partial
  charges for any non-neutral species. Always tell the user to
  double-check the formal charge of their molecule.

## §4. Engine selection

`run_amber.py` picks engines in this order, taking the first one on
PATH:

1. **`pmemd.cuda`** — GPU production. AmberTools25 ships it open-
   source; older Amber required a paid license (no longer relevant).
   Roughly 50–200× faster than sander for typical small-molecule
   systems on a single A100.
2. **`pmemd`** — multi-threaded CPU production. Use when no GPU
   available; 5–20× faster than sander.
3. **`sander`** — reference engine. Slow but bulletproof; useful for
   minimization (where the speed difference is small) and for any
   diagnostic step where you want the documented reference behaviour.

Override with `--engine sander` (testing) or `--engine pmemd.cuda`
(force GPU even if pmemd is also present).

If the user has both `pmemd.cuda` and `pmemd` on PATH and is running
on a CPU-only node, **the auto-selection picks `pmemd.cuda` and the
job will fail at runtime** with a CUDA initialization error. Use
`--engine pmemd` explicitly in that case. (v1.3 does not probe the
host for actual GPU availability before selecting; that's a v2.4
nice-to-have.)

## §5. Known failure modes

- **antechamber silently fails on aromatic perception.** If the input
  structure has unusual valence states (e.g., a carbene, a nitrene,
  any radical), antechamber may produce a `.mol2` with wrong bond
  orders that `parmchk2` then can't generate parameters for. Symptom:
  tleap errors with "could not find atom type". Workaround: pre-clean
  the structure with OpenBabel or Chem3D, or run antechamber
  manually with `-fi mol2` from a known-good mol2.
- **Wrong `--net-charge`.** AM1-BCC charges are off by a constant
  per-atom shift if the net charge is wrong. Symptom: total partial
  charge in the mol2 doesn't match the formal charge; system slowly
  blows up during heating. Fix: verify the formal charge from a
  Lewis structure and re-run.
- **Box too small.** A 12 Å buffer is the AmberMD tutorial standard
  but for highly anisotropic molecules (long, flat) the box can end
  up too small in one dimension. Symptom: production-MD stage
  reports image-of-image close contact warnings. Fix: re-parameterize
  with `--buffer 15.0` or larger.
- **Truncated octahedron not used.** v1.3 uses rectangular boxes
  (`solvateBox`, not `solvateOct`). For rotationally symmetric
  systems an octahedron saves ~20–30% of the solvent atoms; we
  trade that efficiency for predictable downstream behaviour. Edit
  the tleap deck by hand if you need an octahedron.
- **Engine mismatch on CPU-only nodes** — see §4 above.
- **`pmemd.cuda` OOM at large box sizes.** A 40 GB GPU runs out of
  memory around 100k–200k atoms depending on the model. Symptom:
  CUDA OOM error in `prod.mdout`. Fix: reduce buffer or split
  trajectory across multiple shorter runs.

## §6. Troubleshooting

- **"could not find atom type" in tleap.log** — antechamber produced
  a typed mol2 with an atom type GAFF2 doesn't know. Check the
  antechamber `--keep-intermediates` output; usually a structure
  cleanliness issue (radicals, hypervalent atoms, missing hydrogens).
- **Heat stage produces NaN** — almost always charge parity (wrong
  `--net-charge`) or unconstrained hydrogens (someone removed
  `ntc=2, ntf=2` from the mdin). Less commonly, a bad starting
  structure with overlapping atoms; run minimization longer.
- **Density stage drifts away from 1 g/cm³** — expected for ~100 ps
  on small boxes; should converge within ~200 ps. If it doesn't, the
  buffer is probably too small (§5) or the temperature is too high.
- **`pmemd.cuda` runs but production trajectory shows energy drift** —
  check `cut=10.0` in the mdin; some users default to 8 Å which is
  too tight for charged species and produces drift.
- **MDAnalysis can't read the .nc file** — install netCDF support
  (`pip install netCDF4`); ASE's reader is fine but MDAnalysis's
  default does not include the binary backend on every install.

## §7. Out of scope (v1.3)

These are not in v1.3 and are not blocking issues — they are scope
decisions:

- **Protein and nucleic-acid MD** with ff19SB+OPC, ff14SB, OL21 —
  v2.3.
- **Free-energy methods** (TI / FEP / MBAR / SLEEK).
- **Enhanced sampling** (REMD, accelerated MD, metadynamics, AWH).
- **QM/MM** with sander/quick or external QM engines.
- **Umbrella sampling** and constrained-coordinate schemes.
- **Constant-pH MD** or any titration protocol.
- **NPT with anisotropic barostat** — v1.3 uses isotropic Berendsen
  (`ntp=1, taup=2.0`), which is fine for solution-phase but wrong
  for crystals or membranes. Edit the mdin manually if needed.
- **SLURM submission** — v1.3 prints the engine command; the user
  wraps it in a queue script. v2.4 may add submission templates.
