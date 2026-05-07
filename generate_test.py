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

# 1. caffeine.xyz — a single organic molecule, used for prompt 1
#    ASE doesn't ship caffeine in molecule(); use a small drug-like molecule instead
#    or build caffeine from SMILES if you have rdkit. Easiest: use aspirin's
#    geometry from a cheaper source, or just use a smaller named molecule.
#    For testing the skill, exact identity doesn't matter — pick something organic.
caffeine_proxy = molecule("CH3CH2OH")  # ethanol stands in fine for triggering tests
write("test-inputs/caffeine.xyz", caffeine_proxy)
# (If you want real caffeine, paste a known xyz block from PubChem. The skill
#  doesn't care; the prompt just references the filename.)

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