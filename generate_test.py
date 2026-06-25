# generate_test_inputs.py
# Run once to create all test files for Layer B testing.
import os
import numpy as np
from ase import Atoms
from ase.build import molecule, bulk, fcc111, add_adsorbate
from ase.io import write
from ase.calculators.lj import LennardJones
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.verlet import VelocityVerlet
from ase import units

os.makedirs("test-inputs", exist_ok=True)

# 1. caffeine.xyz — real caffeine (C8H10N4O2, 24 atoms), referenced by many prompts.
#    An earlier revision used an ethanol stand-in here ("exact identity doesn't
#    matter"), but the skills now inspect the structure and correctly flag that a
#    9-atom C2H6O file labelled "caffeine" is mismatched — which derails the
#    trigger tests into clarifying questions (and, in headless `claude -p`, hangs).
#    So ship the real molecule. Geometry is an RDKit ETKDGv3 + MMFF94 conformer
#    (seed 42), embedded verbatim so regenerating fixtures needs no rdkit.
_CAFFEINE_XYZ = """24
caffeine C8H10N4O2 (RDKit ETKDGv3 + MMFF94, seed 42)
C      3.297553     0.390073     0.206451
N      2.113339    -0.419425     0.070900
C      2.071817    -1.786848    -0.000597
N      0.836093    -2.230041    -0.122033
C      0.070906    -1.103102    -0.127378
C      0.824887     0.024878    -0.010538
C      0.270942     1.333427     0.010154
O      0.959608     2.343913     0.115886
N     -1.122540     1.332859    -0.101901
C     -1.809264     2.609651    -0.093467
C     -1.937588     0.187773    -0.224509
O     -3.164541     0.289861    -0.318066
N     -1.297715    -1.052087    -0.234867
C     -2.063721    -2.278817    -0.357601
H      3.221969     0.965167     1.132629
H      4.178366    -0.256019     0.245053
H      3.365960     1.054451    -0.658519
H      2.959652    -2.405529     0.039943
H     -1.124128     3.455358     0.003783
H     -2.373952     2.715919    -1.025583
H     -2.516131     2.627771     0.742605
H     -1.884045    -2.902039     0.524175
H     -1.740874    -2.813264    -1.256685
H     -3.136592    -2.083930    -0.434139
"""
with open("test-inputs/caffeine.xyz", "w") as _f:
    _f.write(_CAFFEINE_XYZ)

# 2. cluster.xyz — water cluster of 12 molecules, used for prompt 2 (the "relax" test)
#    Build by replicating a single water in a loose cube with random offsets.
np.random.seed(0)
waters = []
for i in range(12):
    w = molecule("H2O")
    w.translate(np.random.uniform(-5, 5, size=3))
    waters.append(w)
cluster = waters[0]
for w in waters[1:]:
    cluster += w
write("test-inputs/cluster.xyz", cluster)

# 3. ar108.xyz — 108-atom argon cluster as starting config, used for prompt 3
ar = bulk("Ar", "fcc", a=5.26, cubic=True).repeat((3, 3, 3))
write("test-inputs/ar108.xyz", ar)

# 4. md.traj — a short LJ trajectory, used for prompt 4 (analysis test)
#    Need this to be a real trajectory the skill's analyze_traj.py can read.
ar_md = ar.copy()
ar_md.calc = LennardJones()
MaxwellBoltzmannDistribution(ar_md, temperature_K=90)
dyn = VelocityVerlet(ar_md, timestep=2 * units.fs, trajectory="test-inputs/md.traj")
dyn.run(500)  # 1 ps, enough for RMSD/energy-drift to be meaningful
print("Generated all test inputs in ./test-inputs/")