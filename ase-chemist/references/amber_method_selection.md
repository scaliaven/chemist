# Amber method-selection rules (v1.3)

Part of the v1.3 Amber reference set. Companion files:
[`amber_carveout.md`](amber_carveout.md),
[`amber_pipeline.md`](amber_pipeline.md),
[`amber_force_fields.md`](amber_force_fields.md),
[`amber_failure_modes.md`](amber_failure_modes.md). Index:
[`amber.md`](amber.md).

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

## Method-selection rules

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
