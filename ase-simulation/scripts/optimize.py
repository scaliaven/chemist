#!/usr/bin/env python3
"""Geometry optimization with BFGS or FIRE.

When to use:
    The user wants the relaxed geometry of a structure ("minimize", "optimize",
    "relax", "what's the equilibrium geometry of..."), or you need to prepare
    inputs for vibrational / NEB / single-point analysis. This script logs
    convergence and writes both the optimized structure and the optimization
    trajectory.

When NOT to use:
    For a one-off three-line BFGS in an interactive session, write the code
    inline — the only thing this script adds is argparse and a clean output
    layout. For NEB or constrained minimization, write inline code; the
    constraint API does not fit a CLI cleanly.

Examples:
    # Optimize H2O with EMT (toy)
    python optimize.py --structure h2o.xyz --calculator emt --output opt.xyz

    # Production: tblite GFN2-xTB, FIRE, tight convergence
    python optimize.py --structure mol.xyz --calculator xtb \\
        --xtb-method GFN2-xTB --optimizer fire --fmax 0.01 --output opt.traj
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def build_calculator(name: str, *, xtb_method: str = "GFN2-xTB",
                     charge: int = 0, multiplicity: int = 1):
    """Construct the requested calculator. Raise on missing dependency."""
    if name == "emt":
        from ase.calculators.emt import EMT
        return EMT()
    if name == "lj":
        from ase.calculators.lj import LennardJones
        return LennardJones()
    if name == "tip3p":
        from ase.calculators.tip3p import TIP3P
        return TIP3P()
    if name == "xtb":
        try:
            from tblite.ase import TBLite
        except ImportError as e:
            raise SystemExit(
                f"tblite calculator unavailable: {e}\n"
                "Run `scripts/check_env.py` to see whether tblite is missing "
                "or installed-but-broken. On HPC/conda systems prefer "
                "`conda install -c conda-forge tblite-python`; on a clean "
                "pip environment, `pip install tblite`. Or pick a different "
                "--calculator."
            ) from e
        return TBLite(method=xtb_method, charge=charge,
                      multiplicity=multiplicity, verbosity=0)
    raise SystemExit(f"Unknown calculator: {name}")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Optimize a structure with BFGS or FIRE.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Calculator choice: emt = EMT (Al/Cu/Ag/Au/Ni/Pd/Pt/H/C/N/O only), "
            "lj = Lennard-Jones, tip3p = TIP3P water, xtb = tblite GFN1/GFN2-xTB."
        ),
    )
    p.add_argument("--structure", required=True,
                   help="Path to input structure (xyz, cif, pdb, traj, ...).")
    p.add_argument("--calculator", required=True,
                   choices=["emt", "lj", "tip3p", "xtb"],
                   help="Energy/force backend.")
    p.add_argument("--xtb-method", default="GFN2-xTB",
                   choices=["GFN1-xTB", "GFN2-xTB"],
                   help="Only used if --calculator=xtb.")
    p.add_argument("--charge", type=int, default=0,
                   help="Net charge (xtb only).")
    p.add_argument("--multiplicity", type=int, default=1,
                   help="Spin multiplicity 2S+1 (xtb only).")
    p.add_argument("--optimizer", default="bfgs",
                   choices=["bfgs", "fire", "lbfgs"],
                   help="bfgs = near-equilibrium, fire = far-from-equilibrium.")
    p.add_argument("--fmax", type=float, default=0.05,
                   help="Force convergence threshold in eV/Å. "
                        "Use 0.01 for vibrations input.")
    p.add_argument("--max-steps", type=int, default=500,
                   help="Maximum optimization steps before giving up.")
    p.add_argument("--output", default="optimized.traj",
                   help="Final geometry (extension determines format). "
                        ".traj preserves energies/forces; .xyz is positions only.")
    p.add_argument("--trajectory", default=None,
                   help="Optimization trajectory (default: derived from --output).")
    p.add_argument("--logfile", default=None,
                   help="Optimization log path (default: stdout).")
    args = p.parse_args()

    from ase.io import read, write

    atoms = read(args.structure)
    print(f"Loaded {len(atoms)} atoms from {args.structure}")
    atoms.calc = build_calculator(
        args.calculator, xtb_method=args.xtb_method,
        charge=args.charge, multiplicity=args.multiplicity,
    )

    if args.optimizer == "bfgs":
        from ase.optimize import BFGS as Opt
    elif args.optimizer == "fire":
        from ase.optimize import FIRE as Opt
    else:
        from ase.optimize import LBFGS as Opt

    traj_path = args.trajectory or str(Path(args.output).with_suffix(".traj"))
    log_path = args.logfile or "-"

    e0 = atoms.get_potential_energy()
    print(f"Initial energy : {e0:.6f} eV")
    f0 = (atoms.get_forces() ** 2).sum(axis=1).max() ** 0.5
    print(f"Initial fmax   : {f0:.4f} eV/Å")
    print(f"Optimizer      : {args.optimizer.upper()} -> fmax={args.fmax} eV/Å, "
          f"max {args.max_steps} steps")

    t_start = time.time()
    opt = Opt(atoms, trajectory=traj_path, logfile=log_path)
    converged = opt.run(fmax=args.fmax, steps=args.max_steps)
    t_elapsed = time.time() - t_start

    e1 = atoms.get_potential_energy()
    f1 = (atoms.get_forces() ** 2).sum(axis=1).max() ** 0.5
    n_steps = opt.get_number_of_steps()

    write(args.output, atoms)

    print()
    print(f"Converged      : {bool(converged)}")
    print(f"Steps          : {n_steps}")
    print(f"Final energy   : {e1:.6f} eV")
    print(f"Final fmax     : {f1:.4f} eV/Å")
    print(f"ΔE             : {(e1 - e0):+.6f} eV")
    print(f"Wall time      : {t_elapsed:.2f} s")
    print(f"Output         : {args.output}")
    print(f"Trajectory     : {traj_path}")

    return 0 if converged else 2


if __name__ == "__main__":
    raise SystemExit(main())
