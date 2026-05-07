# ASE Core Reference

Read this file when you need to: read/write structures, build geometries
programmatically, pick an optimizer, set up an MD integrator, work with
trajectories, or scaffold an NEB.

## Table of contents
1. [Imports and units](#imports-and-units)
2. [Structure I/O](#structure-io)
3. [`ase.build`](#asebuild)
4. [Optimizers](#optimizers)
5. [Molecular dynamics integrators](#molecular-dynamics-integrators)
6. [Trajectory format](#trajectory-format)
7. [Vibrations](#vibrations)
8. [NEB scaffolding](#neb-scaffolding)
9. [Water (TIP3P + FixBondLengths)](#water-tip3p--fixbondlengths)
10. [LJ parameters for real noble gases](#lj-parameters-for-real-noble-gases)

## Imports and units

```python
from ase import Atoms, units
# units.fs           -> 1 femtosecond in ASE-time-units
# units.kB           -> Boltzmann constant in eV/K
# units.Ha, units.Bohr, units.kcal, units.mol  -> common conversions
```

ASE's native units: **eV, Å, ASE-time-unit (~10.18 fs)**. Energies always come
back in eV, forces in eV/Å. Temperature kwargs use `temperature_K=`
(introduced ASE 3.21.0). Time kwargs in code should always be written
as `5.0 * units.fs`, never as raw `0.5`.

## Structure I/O

```python
from ase.io import read, write

atoms = read("input.xyz")              # auto-detect from extension
atoms = read("input.cif")              # CIF crystal
atoms = read("input.pdb")              # PDB
atoms = read("traj.traj", index=-1)    # last frame of an ASE trajectory
frames = read("traj.traj", index=":")  # all frames as a list

write("out.xyz", atoms)
write("out.traj", atoms)               # ASE binary, preserves calc results
write("out.cif", atoms)
write("out.png", atoms)                # quick image
```

Supported formats include `xyz`, `cif`, `pdb`, `traj`, `extxyz`, `vasp`
(POSCAR), `lammps-data`, `gen`, and many more. For a full list, run
`ase info --formats` or read [ase-lib.org/ase/io/io.html](https://ase-lib.org/ase/io/io.html).

When you need atomic charges, energies, or forces preserved alongside
positions, use `.traj` or `extxyz`. Plain `.xyz` is positions-only.

## `ase.build`

```python
from ase.build import molecule, bulk, surface, fcc111, add_adsorbate

# Small molecules from G2/G2-1 dataset
h2o   = molecule("H2O")
ch4   = molecule("CH4")
benz  = molecule("C6H6")

# Bulk crystals
cu    = bulk("Cu", "fcc", a=3.61)
si    = bulk("Si", "diamond", a=5.43)
nacl  = bulk("NaCl", "rocksalt", a=5.64)

# Surface slabs
slab  = fcc111("Pt", size=(4, 4, 4), vacuum=10.0)   # Pt(111) 4x4 surface, 4 layers

# Adsorbate placement
co    = molecule("CO")
add_adsorbate(slab, co, height=2.0, position="ontop")
```

Periodic boundary conditions: `bulk()` and surface builders set `pbc=True`
on the relevant axes. For `molecule()`, PBC is False (no cell) — for MD in
a box you usually want `atoms.center(vacuum=5.0)` or set a cell explicitly.

`molecule()` and `bulk()` cover most starting points. For solvated peptides,
build a PDB elsewhere (PDBFixer is good) and `read()` it.

## Optimizers

| Optimizer | Import | When to use |
|---|---|---|
| BFGS | `from ase.optimize import BFGS` | Default for near-equilibrium structures |
| LBFGS | `from ase.optimize import LBFGS` | Big systems where BFGS Hessian gets expensive |
| FIRE | `from ase.optimize import FIRE` | Far-from-equilibrium, noisy forces, slabs with adsorbates |
| GPMin | `from ase.optimize import GPMin` | Few force calls budget; uses GP surrogate |

Standard pattern:

```python
from ase.optimize import BFGS

opt = BFGS(atoms, trajectory="opt.traj", logfile="opt.log")
opt.run(fmax=0.05)        # fmax in eV/Å
print(f"Final energy: {atoms.get_potential_energy():.4f} eV")
print(f"Max force:    {max((atoms.get_forces()**2).sum(axis=1)**0.5):.4f} eV/Å")
```

Pick `fmax`:
- `0.1 eV/Å` — quick screen
- `0.05 eV/Å` — production geometry
- `0.01 eV/Å` — input to vibrational analysis (otherwise imaginary modes)

## Molecular dynamics integrators

All integrators take an `atoms` object with a calculator attached. Set
initial velocities first if the structure has none:

```python
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
MaxwellBoltzmannDistribution(atoms, temperature_K=300)
```

### NVE — `VelocityVerlet`
```python
from ase.md.verlet import VelocityVerlet
dyn = VelocityVerlet(atoms, timestep=1.0 * units.fs, trajectory="nve.traj")
```
Use to check **energy conservation**. If total energy drifts by more than a
few meV/atom over 10 ps, your timestep is too large or your potential is
discontinuous.

### NVT — `Langevin`
```python
from ase.md.langevin import Langevin
dyn = Langevin(atoms, timestep=1.0 * units.fs,
               temperature_K=300, friction=0.01 / units.fs,
               trajectory="nvt.traj")
```
Default thermostat for general use. Friction `0.01 / fs` couples weakly to
the bath (good for production). `0.1 / fs` for fast equilibration.

### NVT — `NoseHooverChainNVT`
```python
from ase.md.nose_hoover_chain import NoseHooverChainNVT
dyn = NoseHooverChainNVT(atoms, timestep=1.0 * units.fs,
                         temperature_K=300, tdamp=100 * units.fs)
```
Deterministic, conserves a pseudo-Hamiltonian. Use when you want smooth
thermostat behavior (e.g., for spectra) rather than stochastic Langevin.

### NPT — `NPTBerendsen`
```python
from ase.md.nptberendsen import NPTBerendsen
dyn = NPTBerendsen(atoms, timestep=1.0 * units.fs, temperature_K=300,
                   pressure_au=1.01325 * units.bar,
                   compressibility_au=4.57e-5 / units.bar)
```
Berendsen barostat is fine for equilibration; not strictly NPT-distributed,
so don't use it for free energies.

### Running MD with xTB

The integrator does not care which calculator computes forces. To run any
of the ensembles above with xTB, attach a tblite calculator before
constructing the integrator:

```python
from tblite.ase import TBLite
atoms.calc = TBLite(method="GFN2-xTB", verbosity=0)
# then use any integrator above unchanged
```

Practical notes for xTB-driven MD: 1 fs timesteps are fine up to ~ns of
organic-molecule dynamics, but the SCF can drift on long runs — pass
`accuracy=0.1` to TBLite if you see noise in the forces. Wall time is
dominated by the SCF; expect ~10–100 ms/step for a 50-atom organic on a
single core. See `xtb.md` for calculator-side options (charge, multiplicity,
solvation).

### Logging during MD

```python
from ase.md import MDLogger
dyn.attach(MDLogger(dyn, atoms, "md.log",
                    header=True, stress=False, peratom=True),
           interval=100)
```

`interval=100` logs every 100 steps — keep MD logs reasonable in size.

## Trajectory format

```python
from ase.io.trajectory import Trajectory

traj = Trajectory("run.traj", "w", atoms)        # write
dyn.attach(traj.write, interval=100)

# Reading
frames = list(Trajectory("run.traj", "r"))       # list of Atoms
energies = [f.get_potential_energy() for f in frames]
```

`.traj` files store positions, velocities, cell, and `calc.results` per
frame. They are the right thing to write for MD or geometry optimization.

## Vibrations

```python
from ase.vibrations import Vibrations

vib = Vibrations(atoms)
vib.run()                          # writes vib.0x.pckl files
vib.summary()                      # prints frequencies in cm^-1
freqs = vib.get_frequencies()      # numpy array, complex (imaginary -> negative real)
vib.write_jmol()                   # vib.xyz for visualization
vib.clean()                        # remove cached pickles
```

**Important**: optimize to `fmax <= 0.01 eV/Å` first, otherwise low-frequency
modes show up as imaginary (negative).

For thermochemistry (ZPE, free energy at temperature):

```python
from ase.thermochemistry import IdealGasThermo
thermo = IdealGasThermo(vib_energies=vib.get_energies(),
                        potentialenergy=atoms.get_potential_energy(),
                        atoms=atoms, geometry="nonlinear",
                        symmetrynumber=2, spin=0)
G = thermo.get_gibbs_energy(temperature=298.15, pressure=101325.)
```

## NEB scaffolding

For a minimum-energy path between two known endpoints `initial` and `final`:

```python
from ase.mep import NEB
from ase.optimize import FIRE

n_images = 7
images = [initial.copy() for _ in range(n_images)]
images[0]  = initial
images[-1] = final
neb = NEB(images, climb=True)
neb.interpolate()                  # straight-line guess

# Each intermediate image needs its own calculator
for img in images[1:-1]:
    img.calc = make_calculator()   # one fresh instance per image

opt = FIRE(neb, trajectory="neb.traj")
opt.run(fmax=0.05)
```

Use `climb=True` to converge the saddle point precisely (CI-NEB). Each image
needs an **independent** calculator instance — sharing one corrupts forces.

## Water (TIP3P + FixBondLengths)

TIP3P is a **rigid-body** water model: the O–H bond length and H–O–H angle
are fixed by parameterization, not by potential terms. ASE's `TIP3P()`
calculator computes Coulomb + Lennard-Jones contributions but does **not**
constrain the geometry on its own. If you let the bonds flex, the Coulomb
term over-attracts and the water molecules collapse within a few hundred
fs. You must attach `ase.constraints.FixBondLengths` for both O–H bonds
and the H–H "bond" (the third constraint pins the angle) on every water.

```python
from ase.calculators.tip3p import TIP3P
from ase.constraints import FixBondLengths

# `atoms` is a box of N water molecules, ordered (O, H, H, O, H, H, ...)
n_waters = len(atoms) // 3
pairs = []
for i in range(n_waters):
    o, h1, h2 = 3 * i, 3 * i + 1, 3 * i + 2
    pairs += [(o, h1), (o, h2), (h1, h2)]
atoms.set_constraint(FixBondLengths(pairs))
atoms.calc = TIP3P()
# now safe to run optimize / MD
```

Notes:
- **Atom ordering matters.** The (O, H, H) triplet pattern above is what
  `ase.build.molecule("H2O")` produces and what TIP3P assumes. If your
  input is a PDB or arbitrary XYZ, check `atoms.get_chemical_symbols()`
  before assuming the pattern.
- **Combine with `ase.md.langevin.Langevin` for NVT**, default 1 fs
  timestep. Constrained MD with the bundled `scripts/run_md.py` will
  honor whatever constraints are already on the `atoms` object — but the
  script does **not** attach them itself, by design (water-detection in a
  CLI is brittle).
- For **one-off relaxations or single-points on small water clusters**,
  GFN2-xTB is simpler — no constraints to set up. See `xtb.md`.

## LJ parameters for real noble gases

ASE's `LennardJones()` defaults are **reduced units** — ε = 1 eV, σ = 1 Å —
which are toy parameters, not physical. For any real noble-gas simulation
pass `--epsilon` / `--sigma` (and `--rc`) to `scripts/optimize.py`,
`scripts/run_md.py`, or `scripts/single_point.py`. Without them, the
script prints a `[lj] reduced units (ε=1, σ=1) — toy parameters` warning
on startup so you don't accidentally publish reduced-unit "results."

Standard 12-6 LJ parameters for the lighter noble gases:

| Species | ε (eV)   | σ (Å)  | ε/k_B (K) | Source                                        |
|---------|----------|--------|-----------|-----------------------------------------------|
| Ar      | 0.01032  | 3.405  | 119.8     | Rahman, *Phys. Rev.* **136**, A405 (1964)     |
| Kr      | 0.01411  | 3.633  | 163.8     | Maitland & Smith compilation, *IJT* (1980s)   |
| Xe      | 0.01997  | 3.961  | 231.7     | Maitland & Smith compilation, *IJT* (1980s)   |

Values are good to ~5%. The Ar parameters are the bedrock Rahman 1964
fit and are the right default for "liquid argon at 90 K" reproductions.
Kr and Xe values come from Maitland-Smith-Rigby-Wakeham, *Intermolecular
Forces*, OUP (1981) compilations as cited in textbook reviews; primary
sources (transport-property fits, second-virial fits) give values that
differ at the few-percent level — verify against your source of truth
before publishing. ε/k_B is shown for cross-reference with statistical-
mechanics textbooks that quote temperatures.

**Cutoff rule.** The default `rc = 3 σ` is fine for cluster systems and
non-periodic boxes. For periodic systems, ASE's LJ uses the minimum-image
convention, which requires **`rc < L/2`** along every cell vector — pass
`--rc` explicitly if `3 σ` exceeds half your shortest box side, otherwise
forces will be discontinuous and energy conservation will fail.

**Worked example — liquid Ar at 90 K, NVT, 20 ps:**

```bash
python scripts/run_md.py --structure ar108.xyz --calculator lj \
    --epsilon 0.01032 --sigma 3.405 --rc 6.0 \
    --ensemble nvt-langevin --temperature 90 --friction 0.01 \
    --timestep 5.0 --n-steps 4000 \
    --output ar_nvt.traj --logfile ar_nvt.log
```

5 fs is safe for argon (no light atoms, no high-frequency bonds);
`rc = 6.0 Å` is well under L/2 for the 108-atom 3×3×3 fcc cell (a ≈ 5.26 Å,
L = 15.78 Å, L/2 = 7.89 Å) and a bit under the textbook 3 σ ≈ 10.2 Å
cutoff — the small box forces the truncation.

## Appendix: system-size scaling notes

Rough guide to which calculator stays usable at which size, on a single
modern CPU. Use these only to sanity-check the calculator chosen by
SKILL.md's method-selection rules — not as the primary picker.

| Atoms | What's still tractable | Notes |
|---|---|---|
| 1–50 | tblite GFN2-xTB (everything) | Quantum-mechanical observables, fast. Use for production. |
| 50–500 | tblite GFN1/GFN2-xTB (everything) | GFN1 more robust for transition metals. |
| 500–5,000 | EMT/LJ/TIP3P for any task; xTB only for short MD or single-points | xTB scales O(N³); MD past ~1k atoms gets slow. |
| 5,000–50,000 | Built-in classical only (EMT, LJ, TIP3P) | xTB MD is impractical here. |
| > 50,000 | Out of scope for v1 | Needs proper MM (Amber/OpenMM, v2) or an ML potential (v2). |
