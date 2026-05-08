# Amber failure modes, troubleshooting, and out-of-scope (v1.3)

Part of the v1.3 Amber reference set. Companion files:
[`amber_carveout.md`](amber_carveout.md),
[`amber_method_selection.md`](amber_method_selection.md),
[`amber_pipeline.md`](amber_pipeline.md),
[`amber_force_fields.md`](amber_force_fields.md). Index:
[`amber.md`](amber.md).

## Known failure modes

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
- **Engine mismatch on CPU-only nodes** — see the engine-selection
  section in [`amber_force_fields.md`](amber_force_fields.md).
- **`pmemd.cuda` OOM at large box sizes.** A 40 GB GPU runs out of
  memory around 100k–200k atoms depending on the model. Symptom:
  CUDA OOM error in `prod.mdout`. Fix: reduce buffer or split
  trajectory across multiple shorter runs.

## Troubleshooting

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
  buffer is probably too small (see failure modes above) or the
  temperature is too high.
- **`pmemd.cuda` runs but production trajectory shows energy drift** —
  check `cut=10.0` in the mdin; some users default to 8 Å which is
  too tight for charged species and produces drift.
- **MDAnalysis can't read the .nc file** — install netCDF support
  (`pip install netCDF4`); ASE's reader is fine but MDAnalysis's
  default does not include the binary backend on every install.

## Out of scope (v1.3)

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
