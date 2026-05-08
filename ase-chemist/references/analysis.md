# Trajectory Analysis Reference

Read this file when the user wants to extract observables from a simulation
trajectory: RMSD, RMSF, RDF, energy drift, density, pair distribution
functions, or any time-series of a molecular property.

## Table of contents
1. [ASE built-in readers vs MDAnalysis — when to pick which](#ase-vs-mdanalysis)
2. [Loading trajectories](#loading-trajectories)
3. [RMSD](#rmsd)
4. [RMSF](#rmsf)
5. [Radial distribution function (RDF)](#rdf)
6. [Energy drift](#energy-drift)
7. [Common pitfalls](#common-pitfalls)

## ASE vs MDAnalysis

**Use ASE's built-in trajectory readers when:**
- The trajectory is `.traj` (ASE binary) — no other tool reads it natively.
- You need calculator results (energies, forces) per frame.
- The system is small (<10k atoms) and you want simple per-frame analysis.

**Use MDAnalysis when:**
- The trajectory is from another package (DCD, XTC, NetCDF, LAMMPS).
- You need selection language (`"protein and name CA"`, `"resid 5:20"`).
- You want fast vectorized analysis over long trajectories.

`scripts/analyze_traj.py` works with `.traj` and `.xyz` via ASE; for DCD/XTC
fall back to MDAnalysis manually.

## Loading trajectories

### ASE
```python
from ase.io import read
frames = read("run.traj", index=":")    # list[Atoms]
positions = [f.positions for f in frames]
energies  = [f.get_potential_energy() for f in frames]
```

### MDAnalysis
```python
import MDAnalysis as mda
u = mda.Universe("topology.pdb", "trajectory.dcd")
ca = u.select_atoms("name CA")
for ts in u.trajectory:
    print(ts.frame, ca.positions.mean(axis=0))
```

## RMSD

Root-mean-square deviation of positions vs. a reference (typically frame 0,
or an experimental crystal structure).

### ASE-only path

```python
import numpy as np
from ase.io import read

frames = read("run.traj", index=":")
ref = frames[0].positions

# Optional: align each frame to ref using the Kabsch algorithm
# (ASE doesn't ship Kabsch — use scipy or write inline)
def kabsch_align(P, Q):
    # P -> aligned to Q
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    H = Pc.T @ Qc
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return Pc @ R.T + Q.mean(0)

rmsds = []
for f in frames:
    aligned = kabsch_align(f.positions, ref)
    rmsds.append(np.sqrt(((aligned - ref) ** 2).sum(1).mean()))
```

### MDAnalysis path (preferred for proteins)

```python
from MDAnalysis.analysis.rms import RMSD
R = RMSD(u, u, select="name CA", ref_frame=0)
R.run()
# R.results.rmsd has columns [frame, time, RMSD_Å]
```

## RMSF

Per-atom (or per-residue) fluctuation around the mean position over a
trajectory. Telegraphs which atoms are floppy.

### MDAnalysis

```python
from MDAnalysis.analysis.rms import RMSF
ca = u.select_atoms("name CA")
rmsf = RMSF(ca).run()
# rmsf.results.rmsf  — array of length n_atoms in selection
```

### ASE inline

```python
import numpy as np
positions = np.stack([f.positions for f in frames])     # (n_frames, n_atoms, 3)
mean_pos  = positions.mean(axis=0)
rmsf      = np.sqrt(((positions - mean_pos) ** 2).sum(-1).mean(0))   # (n_atoms,)
```

For RMSF to be meaningful, **align each frame first** (Kabsch). Otherwise
overall translation/rotation contaminates the per-atom number.

## RDF

Pair correlation function `g(r)` between two atom types. The classic
"is this liquid structured" diagnostic.

### ASE

```python
from ase.geometry.analysis import Analysis
ana = Analysis(frames)                  # frames is list[Atoms]
rdf, dists = ana.get_rdf(rmax=6.0, nbins=200, elements=("O", "O"),
                         return_dists=True)
# rdf is list[ndarray]; one entry per frame. Average across time:
import numpy as np
rdf_mean = np.mean(rdf, axis=0)
```

`rmax` must be smaller than half the shortest cell vector — RDF beyond
that wraps around the box and is meaningless.

### MDAnalysis

```python
from MDAnalysis.analysis.rdf import InterRDF
o1 = u.select_atoms("name O")
rdf = InterRDF(o1, o1, nbins=200, range=(0.5, 6.0))
rdf.run()
# rdf.results.bins, rdf.results.rdf
```

## Energy drift

For NVE simulations, the total energy should be (approximately) conserved.
Drift > a few meV/atom over 10 ps means the timestep is too large or the
potential has discontinuities.

```python
import numpy as np
from ase.io import read
frames = read("nve.traj", index=":")

E_kin = np.array([f.get_kinetic_energy() for f in frames])
E_pot = np.array([f.get_potential_energy() for f in frames])
E_tot = E_kin + E_pot

drift_meV_per_atom = 1000 * (E_tot - E_tot[0]) / len(frames[0])
print(f"Max |drift| = {abs(drift_meV_per_atom).max():.3f} meV/atom")
```

For NVT (Langevin/Nose-Hoover), the conserved quantity is not total
energy — Langevin couples to a bath. The right diagnostic is **temperature
equilibration**: plot instantaneous T vs. time and confirm it fluctuates
around the target.

## Common pitfalls

- **Forgetting alignment.** RMSF and RMSD without alignment include the
  bulk motion of the system through space.
- **Periodic unwrapping.** Across PBC, atoms can jump by a cell vector.
  For ASE: `atoms.set_positions(atoms.get_positions(wrap=False))` before
  computing displacements; for MDAnalysis use `transformations.unwrap`.
- **First frame biases.** "RMSD vs frame 0" using a non-equilibrated frame
  exaggerates everything. Use a reference from after equilibration, or
  the experimental structure if available.
- **RDF normalization.** Both `ase.geometry.analysis.Analysis` and MDAnalysis
  return properly normalized `g(r)`. If you wrote your own histogram,
  remember to divide by `4πr²ρ dr`.
- **Too few frames.** RDFs are noisy for < 100 frames. RMSF needs at least
  a few correlation times. If the trajectory is short, say so in the report.
- **Energy drift on NVT.** Total energy drifts on NVT by design (the bath
  exchanges energy). Don't report NVT energy drift as a stability metric.
