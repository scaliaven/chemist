# xTB Reference (via tblite)

Read this file when the user wants real chemistry on small-to-medium
systems (1–500 atoms, organic/main-group): geometry optimization, MD,
vibrational analysis, HOMO-LUMO gaps, dipole moments, or partial charges.

For running MD with the xTB calculator, see `ase_core.md` §Running MD
with xTB — that page owns the integrator API; this page owns calculator
construction and accuracy notes.

## Install

The supported route is **tblite**:

```bash
pip install tblite
```

`xtb-python` (older) is deprecated upstream and we do not use it.

For GFN0 and GFN-FF you also need the standalone `xtb` binary from the
Grimme group. On Linux/macOS:

```bash
conda install -c conda-forge xtb       # easiest
# or download a static build from https://github.com/grimme-lab/xtb/releases
```

`scripts/check_env.py` checks `shutil.which("xtb")` and reports both routes.

## Two ways to run xTB

| Route | Methods | Pro | Con |
|---|---|---|---|
| **tblite** Python (`from tblite.ase import TBLite`) | GFN1-xTB, GFN2-xTB | Fast, in-process, ASE-native | No GFN0, no GFN-FF |
| Standalone **xtb** binary, called via shell or `ase.calculators.xtb` shim | GFN0, GFN1, GFN2, GFN-FF | All methods, including GFN-FF for big systems | Process startup cost, file I/O |

For v1 prefer tblite. Reach for the standalone binary only when GFN-FF or
GFN0 is needed.

## Method choice

| Method | Cost | When to use |
|---|---|---|
| **GFN-FF** | Cheapest (force-field-like) | Large organic systems (1k+ atoms) where you want better-than-classical for free. Geometry only — no electronic observables. |
| **GFN0-xTB** | Very cheap | Quick screens, periodic systems where GFN1/2 struggle. Less accurate than GFN1/2. |
| **GFN1-xTB** | Cheap | More robust for transition metals than GFN2; older but still useful. |
| **GFN2-xTB** | Default — moderate | Best general-purpose semi-empirical. Use for organics, main-group, vibrations, HOMO-LUMO. |

**Default to GFN2-xTB.** Switch to GFN1 only if GFN2 fails for the system
(transition metals, weird convergence) or the user asks.

## Minimal usage

```python
from ase.build import molecule
from tblite.ase import TBLite

atoms = molecule("H2O")
atoms.calc = TBLite(method="GFN2-xTB")

energy  = atoms.get_potential_energy()      # eV
forces  = atoms.get_forces()                # eV/Å
dipole  = atoms.get_dipole_moment()         # e·Å
```

With a charge or open-shell system:

```python
atoms.calc = TBLite(method="GFN2-xTB",
                    charge=-1,           # net charge
                    multiplicity=1,      # 2S+1
                    accuracy=1.0,        # tighten with 0.1 if needed
                    max_iterations=250,
                    verbosity=0)
```

For optimization, pair with a standard ASE optimizer:

```python
from ase.optimize import BFGS
atoms.calc = TBLite(method="GFN2-xTB")
BFGS(atoms, trajectory="opt.traj").run(fmax=0.01)
```

## Observables xTB exposes

After a force evaluation, `atoms.calc.results` typically contains:

| Key | Meaning | Units |
|---|---|---|
| `energy` | Total energy | eV |
| `forces` | Atomic forces | eV/Å |
| `dipole` | Dipole moment vector | e·Å |
| `charges` | Mulliken charges (if requested) | e |
| `bond_orders` | Wiberg bond orders | dimensionless |
| `stress` | Stress tensor (periodic) | eV/Å³ |

For HOMO-LUMO and orbital energies, use `tblite.interface.Calculator`
directly (the ASE wrapper hides the orbital data). Pattern:

```python
from tblite.interface import Calculator
tb = Calculator("GFN2-xTB", atoms.numbers, atoms.positions)
res = tb.singlepoint()
eigs = res.get("orbital-energies")        # Hartree
occs = res.get("orbital-occupations")     # 0..2 per orbital
```

`scripts/single_point.py` does this for you and reports the gap in eV.

### HOMO-LUMO: tblite vs the `xtb` binary

These two tools report **different numbers** for the same molecule, and the
disagreement can be huge for small systems. You need to know which one
matches the literature value the user is comparing against.

| Source | What "HOMO-LUMO" means | H₂O / GFN2-xTB result |
|---|---|---|
| tblite raw eigenvalues (`orbital-energies`) | E(LUMO) − E(HOMO), no smoothing | **~78.7 eV** |
| `xtb` binary "HL-Gap" line | Fermi-smeared / softened; matches papers | **~13 eV** |

Why the H₂O case is so dramatic: GFN2-xTB uses a minimum valence basis. For
H₂O there are exactly 6 orbitals (4 occupied + 2 virtuals), and the lowest
virtual is a hard antibonding O–H σ\* at +66 eV. The `xtb` binary's "HL-Gap"
applies post-processing that produces a chemically meaningful gap matching
density-of-states reasoning.

For larger molecules with more virtuals, the two numbers converge. For small
systems, they diverge wildly.

**Practical guidance:**
- If the user's expected number comes from the `xtb` binary's stdout,
  call the binary (`shutil.which("xtb")`) and parse its "HL-Gap" line.
- If the user wants the raw eigenvalue gap (e.g., for a method comparison
  or for input to TDDFT-like corrections), use tblite as shown above.
- Either way, **report the convention you used** — don't just print a
  number labeled "HOMO-LUMO".

## Known limits

- **Transition metals**: GFN2 can fail (SCC convergence, wrong spin states).
  Try GFN1 first; for production accuracy on TM chemistry, you need DFT.
- **Periodic systems**: GFN1/GFN2 in tblite have limited PBC support — works
  for molecular crystals and simple solids, fails or is unsupported for
  metallic surfaces. Check the warning printed at calculator setup.
- **Heavy elements**: parameterization stops at radon-ish (Z<=86). Beyond
  that, xTB gives nonsense.
- **Excited states / TDDFT**: not in xTB. For excitations use a real DFT/TDDFT
  code (out of scope for v1).
- **MD stability**: see `ase_core.md` §Running MD with xTB.
- **Spin**: `multiplicity` accepts 2S+1; tblite handles open-shell via
  fractional occupation, which is fine for radicals but not for true
  multireference systems.

## When xTB is the wrong tool

Tell the user honestly:
- System has > ~1000 atoms and they want MD beyond a picosecond → use a
  classical force field (Amber/OpenMM, v2) or a fast ML potential (v2).
- They need transition-metal catalysis chemistry quantitatively → DFT
  (Gaussian/ORCA/VASP, v2).
- They need solvent effects on a reaction → tblite supports a simple ALPB
  solvation model (`solvation="alpb(water)"`); for explicit solvation use
  TIP3P clusters.
