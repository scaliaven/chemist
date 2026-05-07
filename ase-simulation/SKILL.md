---
name: ase-simulation
description: Use this skill whenever the user wants to run, set up, or analyze atomistic simulations on molecules or materials. This covers: molecular dynamics (MD, NVE, NVT, NPT, Langevin, Nose-Hoover) including thermalization, equilibration, and "warm up the system" requests; geometry optimization, energy minimization, or relaxation (BFGS, FIRE, LBFGS — "minimize this molecule", "relax this structure", "find the equilibrium geometry"); vibrational frequency, normal-mode, Hessian, and zero-point-energy analysis; NEB and transition-state searches; structure building (small molecules, bulk crystals, surfaces like fcc111, slabs with adsorbates); trajectory analysis (RMSD, RMSF, RDF, energy drift); single-point energy and force evaluation; binding, interaction, and adsorption energy calculations; and electronic observables like HOMO-LUMO gap, dipole moment, or Mulliken charges. Use this skill for any request involving force fields, semi-empirical methods (xTB / GFN1 / GFN2), DFT-style reasoning about which method to pick, or any computational chemistry / materials task that mentions ASE, EMT, Lennard-Jones, TIP3P, tblite, or xtb. Reach for this skill even when the user does not name ASE — phrases like "minimize this molecule", "relax this geometry", "thermalize at 300 K", "equilibrate the system", "compute the binding energy", "run MD on water", "build a Pt(111) slab", and "compute frequencies" should all trigger this skill.
license: MIT
---

# ASE Simulation Skill (v1)

## Always do this first

Before any non-trivial task, run:

```bash
python scripts/check_env.py
```

It prints which calculators and analysis tools are actually installed, and
ends with a one-line "what you can run right now" summary. **Recommend a
method that the environment supports** — do not ask the user to install xTB if
EMT or LJ already covers the question.

If a backend is missing and the user wants it, prefer the conda install on
HPC / conda systems:

```bash
conda install -c conda-forge ase tblite-python mdanalysis matplotlib
```

…and pip only when conda isn't available:

```bash
pip install ase tblite mdanalysis matplotlib
```

`tblite` ships GFN1-xTB and GFN2-xTB and is the supported successor to the
deprecated `xtb-python`. If `check_env.py` reports `[BROKEN] tblite ...
C extension unloadable`, the pip wheel is libgfortran-incompatible — switch
to `conda install -c conda-forge tblite-python`. The standalone `xtb`
binary (Grimme group) adds GFN0 and GFN-FF if it's on PATH.

## Method selection

Walk these three steps in order. Each rule names *what* to do and *why*; if
the user's case doesn't fit the "because", the rule probably doesn't apply
and you should keep walking.

### Step 1 — what task is this?

| Task | Tool | Notes |
|---|---|---|
| Optimize / minimize / relax | `scripts/optimize.py` | FIRE for far-from-equilibrium, BFGS otherwise |
| MD at temperature T | `scripts/run_md.py` | Langevin NVT is the default ensemble |
| Vibrations / Hessian / ZPE | `ase.vibrations.Vibrations` inline | Optimize to fmax ≤ 0.01 first, or you get spurious imaginary modes |
| HOMO-LUMO / dipole / charges | `scripts/single_point.py` (with `--calculator xtb`) | Returns gap, dipole, Mulliken charges, bond orders. **HOMO-LUMO is the raw eigenvalue gap — see `references/xtb.md` for the convention.** |
| Binding / interaction / adsorption energy | three runs of `scripts/single_point.py` | E(complex) − E(A) − E(B); use the same calculator for all three |
| Transition state / barrier | NEB inline (see `references/ase_core.md`) | No turnkey script in v1 |
| Build a structure | `ase.build` inline | molecule / bulk / fcc111 / add_adsorbate |
| Analyze a trajectory | `scripts/analyze_traj.py` | RMSD / RMSF / energy drift / optional RDF |

### Step 2 — pick the calculator

Apply the first rule that fits the system, in this order:

1. **If the user explicitly named a calculator** (xTB, EMT, GFN2, TIP3P,
   …), use that one. *Why:* don't second-guess an explicit choice.
2. **If the system contains only EMT-supported metals** (Al, Cu, Ag, Au,
   Ni, Pd, Pt, plus H/C/N/O as adsorbates), prefer **EMT**. *Why:* it's
   free, instant, and the user probably wants a quick metallic-system
   answer.
3. **If the system is pure water** (H₂O molecules only), prefer **TIP3P**.
   *Why:* parameterized for exactly this case.
4. **If the system has organic / main-group chemistry** (heteroatoms,
   non-EMT elements, organic functional groups, ionic bonding), use
   **tblite GFN2-xTB**. *Why:* EMT will silently give nonsense for
   non-metals; GFN2-xTB is the cheapest method that knows real chemistry.
5. **If the system is a transition-metal complex and GFN2 fails to
   converge**, fall back to **GFN1-xTB**. *Why:* GFN1 is more robust on
   d-block elements at the cost of some accuracy.
6. **If the system is large enough that the chosen method becomes
   impractical** (rough cliffs: xTB MD past ~1k atoms, anything past
   ~50k), say so out loud: "v1 can't deliver that — GFN2-xTB MD becomes
   impractical past 1k atoms, and v1 has no classical force field for
   organics. v2 will add Amber and ML potentials; for now we can do a
   single-point or a short geometry optimization, but not production
   MD." See `references/ase_core.md` §Appendix for the full size table.

### Step 3 — confirm the calculator is installed

Read the `[OK]` / `[MISSING]` lines from `scripts/check_env.py`. If your
chosen calculator is `[MISSING]`, ask the user to install it; **do not
silently substitute a wrong-physics fallback**. EMT on an organic is the
classic failure mode — it will return numbers that look fine and are
meaningless.

## Scripts — when to invoke each

All scripts live in `scripts/` and are parameterized via argparse.
Run with `--help` to see options. Reach for the script unless the user
needs custom logic; otherwise write inline ASE code (which is fine — ASE
is concise).

- **`scripts/check_env.py`** — Run at the start of any non-trivial task.
  Reports installed backends and a one-line capability summary.
- **`scripts/optimize.py`** — Geometry optimization with BFGS or FIRE.
  Logs convergence; saves optimized structure and trajectory.
- **`scripts/run_md.py`** — Parameterized MD driver. Calculator (emt / lj /
  tip3p / xtb), ensemble (nve / nvt-langevin / nvt-nose-hoover), T, dt,
  n_steps. Sensible defaults for organic molecules (1 fs, 300 K, friction
  0.01/fs for Langevin, log every 100 steps).
- **`scripts/single_point.py`** — Single-point energy plus xTB electronic
  observables (dipole, Mulliken charges, Wiberg bond orders, HOMO-LUMO).
  Tagged key=value output. Optimize first, then run this — single-point
  observables on a strained geometry are nonsense.
- **`scripts/analyze_traj.py`** — RMSD, RMSF, energy drift, optional RDF.
  Saves PNG plots and CSV data alongside the trajectory.

When inline code is more honest, write inline code — for example, a 5-line
single-point energy calculation or a one-shot `ase.build` does not need a
script.

## References — read these on demand

Each reference file is short and topic-scoped. Read the file when its topic
comes up; do not preload them all.

- **`references/ase_core.md`** — Read for: structure I/O (read/write,
  formats), `ase.build` patterns, optimizer choice, MD integrators and
  their constructor signatures, units (eV / Å / fs / kB), the Trajectory
  format, NEB scaffolding.
- **`references/xtb.md`** — Read for: tblite install, GFN1 vs GFN2 choice,
  the standalone `xtb` binary (GFN0, GFN-FF), what observables xTB
  exposes (energy, forces, dipole, HOMO-LUMO, Mulliken), known
  limitations (transition metals, periodic systems).
- **`references/analysis.md`** — Read for: when to use ASE's built-in
  trajectory readers vs MDAnalysis, recipes for the analyses
  `analyze_traj.py` implements, common pitfalls (alignment, periodic
  unwrapping).

## Defaults and conventions

- **Units**: ASE uses eV, Å, ASE-time-units. Use `ase.units.fs` /
  `ase.units.kB` rather than raw numbers. Temperature kwarg is
  `temperature_K=` (canonical since ASE 3.21.0).
- **Timestep**: 1 fs is safe for organic molecules with all-atom dynamics.
  Bump to 2 fs only if you constrain hydrogen bonds (ASE doesn't do
  RATTLE/SHAKE elegantly, so 1 fs is the safer default).
- **Friction (Langevin)**: 0.01 / fs is a reasonable thermostat coupling
  for production. Higher values (0.1 / fs) for fast equilibration.
- **Optimization tolerance**: `fmax=0.05 eV/Å` for production geometries;
  `0.01 eV/Å` for vibrational analysis input.
- **Trajectory format**: prefer `.traj` (ASE binary, includes calculator
  results) over `.xyz` (positions only) when energies/forces matter
  downstream.
- **Random seed**: Set `seed` in MD integrators if reproducibility matters
  to the user.

## Reporting results

When you finish a task, report:
1. The method used (calculator + integrator/optimizer) and **why** it was
   chosen given system size, available backends, and accuracy needed.
2. Final numbers (energy, fmax, temperature, etc.) with units.
3. Where outputs were written (trajectory, plots, CSVs).
4. Any caveats (e.g., "GFN2-xTB; transition-metal accuracy is limited",
   "NVE energy drift was 0.3 meV/atom over 1 ps — reasonable").

## What v1 does NOT support

Tell the user honestly when their request crosses the line:
- Amber, Gaussian, VASP, Quantum ESPRESSO (planned for v2)
- ML potentials — MACE, CHGNet, ORB, etc. (planned for v2). If a user
  asks for one, say: "v2 will support those; for now GFN2-xTB is in
  the same accuracy ballpark for organics at ~10× the cost."
- Free energy methods, enhanced sampling, metadynamics
- Implicit/explicit solvation models beyond TIP3P water clusters
- SLURM/HPC submission scripts
- Web GUI / visualization servers
