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


def build_calculator(name: str, *, atoms=None, xtb_method: str = "GFN2-xTB",
                     charge: int = 0, multiplicity: int = 1,
                     lj_epsilon: float | None = None,
                     lj_sigma: float | None = None,
                     lj_rc: float | None = None,
                     mace_system_class: str | None = None,
                     mace_device: str | None = None,
                     mace_size: str = "medium"):
    """Construct the requested calculator. Raise on missing dependency."""
    if name == "mace":
        if atoms is None:
            raise SystemExit(
                "build_calculator(name='mace') requires atoms= for "
                "element-based routing."
            )
        from ml_calculator import make_ml_calc
        return make_ml_calc(
            atoms, system_class=mace_system_class,
            device=mace_device, model_size=mace_size,
        )
    if name == "emt":
        from ase.calculators.emt import EMT
        return EMT()
    if name == "lj":
        from ase.calculators.lj import LennardJones
        kwargs = {}
        if lj_epsilon is not None:
            kwargs["epsilon"] = lj_epsilon
        if lj_sigma is not None:
            kwargs["sigma"] = lj_sigma
        if lj_rc is not None:
            kwargs["rc"] = lj_rc
        elif lj_sigma is not None:
            kwargs["rc"] = 3.0 * lj_sigma
        if kwargs:
            eps_s = f"{kwargs.get('epsilon', 1.0):.4g} eV"
            sig_s = f"{kwargs.get('sigma', 1.0):.4g} Å"
            rc_s = (f"{kwargs['rc']:.4g} Å" if "rc" in kwargs
                    else "ASE default")
            print(f"[lj] ε={eps_s}  σ={sig_s}  rc={rc_s}")
        else:
            print("[lj] reduced units (ε=1, σ=1) — toy parameters; "
                  "for real noble gases pass --epsilon/--sigma "
                  "(see references/ase_core.md §LJ parameters)")
        return LennardJones(**kwargs)
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
            "lj = Lennard-Jones, tip3p = TIP3P water, xtb = tblite GFN1/GFN2-xTB, "
            "mace = MACE-MP-0 / MACE-OFF (auto-routed)."
        ),
    )
    p.add_argument("--structure", required=True,
                   help="Path to input structure (xyz, cif, pdb, traj, ...).")
    p.add_argument("--calculator", required=True,
                   choices=["emt", "lj", "tip3p", "xtb", "mace"],
                   help="Energy/force backend. mace = MACE-MP-0 / MACE-OFF "
                        "foundation model (auto-routed by element set).")
    p.add_argument("--xtb-method", default="GFN2-xTB",
                   choices=["GFN1-xTB", "GFN2-xTB"],
                   help="Only used if --calculator=xtb.")
    p.add_argument("--charge", type=int, default=0,
                   help="Net charge (xtb only).")
    p.add_argument("--multiplicity", type=int, default=1,
                   help="Spin multiplicity 2S+1 (xtb only).")
    p.add_argument("--epsilon", type=float, default=None,
                   help="LJ ε in eV (default: ASE reduced units, ε=1). "
                        "For real noble gases see references/ase_core.md "
                        "§LJ parameters.")
    p.add_argument("--sigma", type=float, default=None,
                   help="LJ σ in Å (default: ASE reduced units, σ=1).")
    p.add_argument("--rc", type=float, default=None,
                   help="LJ cutoff in Å (default: 3*sigma if --sigma is "
                        "given, else ASE default). Must be < L/2 in "
                        "periodic systems.")
    p.add_argument("--mace-system-class", default=None,
                   choices=["organic", "materials"],
                   help="Override MACE auto-routing. Default: route by "
                        "element set (organic if all elements in "
                        "H/C/N/O/P/S/F/Cl/Br/I, else materials).")
    p.add_argument("--mace-device", default=None,
                   choices=["cuda", "cpu"],
                   help="Inference device for MACE. Default: auto-detect.")
    p.add_argument("--mace-size", default="medium",
                   choices=["small", "medium", "large"],
                   help="MACE foundation-model checkpoint size.")
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
        args.calculator, atoms=atoms, xtb_method=args.xtb_method,
        charge=args.charge, multiplicity=args.multiplicity,
        lj_epsilon=args.epsilon, lj_sigma=args.sigma, lj_rc=args.rc,
        mace_system_class=args.mace_system_class,
        mace_device=args.mace_device, mace_size=args.mace_size,
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
