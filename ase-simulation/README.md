# ase-simulation (v1)

An Agent Skill for running molecular dynamics, geometry optimization, and
quantum-chemistry calculations using ASE (Atomic Simulation Environment) as
the orchestration layer. This is v1; the design philosophy is **traditional
trusted methods first, ML acceleration as a future extension**.

## Install

**Preferred (conda / HPC):**

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib numpy
```

**Pip-only:**

```bash
pip install ase tblite mdanalysis matplotlib numpy
```

`tblite` provides GFN1-xTB and GFN2-xTB. For GFN0 / GFN-FF you also need the
standalone `xtb` binary on `PATH` (e.g., `conda install -c conda-forge xtb`).

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

## What's in v1

- **Calculators**: ASE built-ins (EMT, Lennard-Jones, TIP3P) and tblite
  (GFN1-xTB, GFN2-xTB).
- **Geometry optimization**: BFGS, FIRE, LBFGS via `scripts/optimize.py`.
- **Molecular dynamics**: NVE (VelocityVerlet), NVT (Langevin or
  Nose-Hoover) via `scripts/run_md.py`.
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
│   ├── ase_core.md       # ASE I/O, build, optimizers, MD integrators, vibrations, NEB
│   ├── xtb.md            # tblite install, GFN1/GFN2/GFN0/GFN-FF, observables, limits
│   └── analysis.md       # trajectory analysis recipes (ASE vs MDAnalysis)
├── scripts/
│   ├── check_env.py      # detect installed backends, capability summary
│   ├── optimize.py       # BFGS/FIRE/LBFGS with convergence reporting
│   ├── run_md.py         # NVE / NVT-Langevin / NVT-Nose-Hoover
│   ├── single_point.py   # E + dipole/charges/HOMO-LUMO via tblite
│   └── analyze_traj.py   # RMSD/RMSF/energy drift/RDF, PNG+CSV outputs
└── evals/
    └── evals.json        # 5 realistic prompts, no automated assertions yet
```

## What's coming in v2

- **External backends**: Amber (classical MM), Gaussian (DFT), Quantum
  ESPRESSO / VASP (plane-wave DFT). These have heavyweight installs and
  need careful UX so we did not bundle them in v1.
- **ML potentials**: MACE-MP, CHGNet, ORB. Powerful, but with sharp
  failure modes (out-of-distribution geometries silently give garbage).
  v2 will add these with explicit OOD-warnings.
- **HPC submission helpers**: SLURM templates, queueing, restart logic.
- **Solvation and free energy**: implicit solvent beyond xTB's ALPB,
  thermodynamic integration, metadynamics.
- **NEB script**: a turnkey CLI for transition-state searches.

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
