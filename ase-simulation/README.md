# ase-simulation (v1.2)

An Agent Skill for running molecular dynamics, geometry optimization, and
quantum-chemistry calculations using ASE (Atomic Simulation Environment) as
the orchestration layer. The design philosophy is **traditional trusted
methods first, ML acceleration as a layered extension** — v1.2 adds MACE
foundation-model support with a mandatory cross-validation contract
against GFN2-xTB so the trusted-methods grounding stays intact.

## Install

**Preferred (conda / HPC):**

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib numpy
```

**Pip-only:**

```bash
pip install ase tblite mdanalysis matplotlib numpy
```

**Optional — MACE foundation models (v1.2+):**

```bash
pip install mace-torch
```

`tblite` provides GFN1-xTB and GFN2-xTB. For GFN0 / GFN-FF you also need the
standalone `xtb` binary on `PATH` (e.g., `conda install -c conda-forge xtb`).
`mace-torch` provides MACE-MP-0 (89-element materials) and MACE-OFF (10-element
organics) foundation models for systems past the xTB size cliff (~1k atoms);
CUDA is strongly recommended (CPU mode is ~10× slower).

> **If pip-installed `tblite` fails with `_gfortran_os_error_at` (or
> similar `undefined symbol` errors), the wheel was built against a newer
> libgfortran than your system has.** Reinstall via conda:
> `conda install -c conda-forge tblite-python`.
> `scripts/check_env.py` reports `[BROKEN]` rather than `[OK]` in that case
> so you can spot it immediately. The `xtb-python` package on conda-forge
> (different from `tblite`) is also available but is deprecated upstream.

After install, sanity check:

```bash
python ase-simulation/scripts/check_env.py
```

## What's in v1.2

- **Calculators**: ASE built-ins (EMT, Lennard-Jones, TIP3P), tblite
  (GFN1-xTB, GFN2-xTB), and **MACE** (MACE-MP-0 for materials, MACE-OFF
  for organics; auto-routed by element set).
- **Geometry optimization**: BFGS, FIRE, LBFGS via `scripts/optimize.py`.
  All five calculator backends supported.
- **Molecular dynamics**: NVE (VelocityVerlet), NVT (Langevin or
  Nose-Hoover) via `scripts/run_md.py`. With MACE,
  **cross-validation against GFN2-xTB runs by default every 1 ps** —
  the run aborts when force MAE exceeds 100 meV/Å. This is the
  contract under which MACE is recommended; see
  `references/ml_potentials.md`.
- **ML cross-validation**: post-hoc validation of any saved MACE
  trajectory via `scripts/validate_ml_md.py`.
- **Vibrational analysis**: `ase.vibrations.Vibrations` (inline code; see
  `references/ase_core.md`).
- **Structure building**: `ase.build` patterns for molecules, bulk crystals,
  and surfaces with adsorbates.
- **NEB scaffolding**: documented in `references/ase_core.md`; no turnkey
  script in v1.
- **Trajectory analysis**: RMSD, RMSF, energy drift, optional RDF via
  `scripts/analyze_traj.py`.

## Layout

```
ase-simulation/
├── SKILL.md              # entrypoint: when to use, method-selection tree
├── README.md             # this file
├── references/
│   ├── ase_core.md        # ASE I/O, build, optimizers, MD integrators, vibrations, NEB
│   ├── xtb.md             # tblite install, GFN1/GFN2/GFN0/GFN-FF, observables, limits
│   ├── analysis.md        # trajectory analysis recipes (ASE vs MDAnalysis)
│   ├── ml_potentials.md   # MACE method-selection, cross-validation contract, failure modes
│   ├── amber.md           # STUB — small-mol GAFF2 lands v2.2; protein/NA v2.3
│   └── gaussian.md        # STUB — v2.4 scope + detection spec; not implemented
├── scripts/
│   ├── check_env.py        # detect installed backends, capability summary, CUDA status
│   ├── optimize.py         # BFGS/FIRE/LBFGS with convergence reporting; supports MACE
│   ├── run_md.py           # NVE / NVT-Langevin / NVT-Nose-Hoover; MACE w/ auto cross-validation
│   ├── single_point.py     # E + dipole/charges/HOMO-LUMO via tblite
│   ├── analyze_traj.py     # RMSD/RMSF/energy drift/RDF, PNG+CSV outputs
│   ├── ml_calculator.py    # MACE factory: auto-routes MACE-OFF vs MACE-MP-0 by elements
│   └── validate_ml_md.py   # post-hoc cross-validation of MACE trajectories vs GFN2-xTB
└── evals/
    └── evals.json        # 5 realistic prompts, no automated assertions yet
```

## What's coming in v2.2 and beyond

- **Amber for small-molecule MD (v2.2)**: GAFF2 + AM1-BCC charges via
  `antechamber`, tleap solvation in TIP3P / OPC, production MD via
  `pmemd` / `pmemd.cuda`. Architecture is shell-out, not ASE-Calculator
  (the ASE Amber calculator is single-point only). See
  `references/amber.md` and `PLAN.md` Phase 2.
- **Amber for biomolecular MD (v2.3)**: ff19SB + OPC for proteins,
  OL21 for nucleic acids, full tleap-from-PDB system prep.
- **More ML potentials (v2.2+)**: CHGNet for charge-aware materials,
  Orb-v3 for richer OOD signal via its built-in confidence head,
  committee-uncertainty heads on frozen MACE-MP-0 backbones.
- **Gaussian DFT (v2.4)**: SP / Opt / Freq / SMD via `ase.calculators.
  gaussian.Gaussian` + cclib for output parsing. License-gated; no
  method/basis defaults — explicit user input required.
- **HPC submission helpers**: SLURM templates, queueing, restart logic.
- **Solvation and free energy**: implicit solvent beyond xTB's ALPB,
  thermodynamic integration, metadynamics.
- **NEB script**: a turnkey CLI for transition-state searches.

The Amber and Gaussian chapters have **stub reference files** in
`references/` that document the intended scope, the detection logic
for each backend, and a list of open questions to be answered by
real-usage data before v2 work begins. The stubs are not
implementations and should not be followed as workflows.
`scripts/check_env.py` reports detection status for these backends in
a `[v2 preview]` block (after the v1 capability summary) so users
can see what is on their box even though the skill cannot drive it
yet. See `PLAN.md` for the full sequencing.

## Notes for skill developers

- v1 was built against ASE current (`temperature_K=` is the canonical
  thermostat kwarg as of ASE 3.21.0) and `tblite` (the supported
  successor to the deprecated `xtb-python`). If you upgrade either,
  re-run the evals manually and update the references.
- The eval set has **no programmatic assertions** in v1. That is iteration
  2's job: pick the assertions that are stable across small numerical
  changes (presence of output files, ranges for energies, sign of
  drift) rather than exact numbers.
- The SKILL.md description is intentionally long and lists the user
  phrases that should trigger this skill (MD, NVT, optimize, HOMO-LUMO,
  RDF, etc.). If trigger reliability is poor, optimize that field first.
