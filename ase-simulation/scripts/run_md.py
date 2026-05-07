#!/usr/bin/env python3
"""Run molecular dynamics with a chosen calculator and ensemble.

When to use:
    The user wants to simulate a molecule or material at temperature T —
    "run MD on water at 300 K", "thermalize this", "watch this molecule
    move", "produce a trajectory for analysis". This script picks the
    integrator, attaches a logger and trajectory writer, and gives you a
    reproducible CLI you can hand back to the user.

When NOT to use:
    For a single-shot MD experiment in a notebook, write inline ASE code.
    For NPT (barostat) or constrained dynamics, write inline — the API
    surface is large and a CLI hides too much. See references/ase_core.md.

Defaults are tuned for organic molecules: 1 fs timestep, 300 K, Langevin
friction 0.01/fs, log every 100 steps. Adjust for metals (5 fs OK with
EMT) or accelerated equilibration (friction 0.1/fs).

Examples:
    # Toy: argon LJ NVE
    python run_md.py --structure ar.xyz --calculator lj --ensemble nve \\
        --n-steps 5000 --output nve.traj

    # Real: organic molecule at 300 K with GFN2-xTB
    python run_md.py --structure mol.xyz --calculator xtb --ensemble nvt-langevin \\
        --temperature 300 --timestep 1.0 --n-steps 10000 --output md.traj
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def build_calculator(name: str, *, xtb_method: str = "GFN2-xTB",
                     charge: int = 0, multiplicity: int = 1,
                     lj_epsilon: float | None = None,
                     lj_sigma: float | None = None,
                     lj_rc: float | None = None):
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
        description="Run NVE / NVT MD with ASE.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Calculator: emt | lj | tip3p | xtb. "
            "Ensemble: nve (VelocityVerlet), nvt-langevin (default), "
            "nvt-nose-hoover (deterministic NVT)."
        ),
    )
    p.add_argument("--structure", required=True,
                   help="Input structure (xyz, cif, pdb, traj, ...).")
    p.add_argument("--calculator", required=True,
                   choices=["emt", "lj", "tip3p", "xtb"])
    p.add_argument("--xtb-method", default="GFN2-xTB",
                   choices=["GFN1-xTB", "GFN2-xTB"])
    p.add_argument("--charge", type=int, default=0)
    p.add_argument("--multiplicity", type=int, default=1)
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
    p.add_argument("--ensemble", default="nvt-langevin",
                   choices=["nve", "nvt-langevin", "nvt-nose-hoover"])
    p.add_argument("--temperature", type=float, default=300.0,
                   help="Target temperature in Kelvin (NVT) and "
                        "Maxwell-Boltzmann initialization temperature (NVE).")
    p.add_argument("--friction", type=float, default=0.01,
                   help="Langevin friction in 1/fs (used by nvt-langevin).")
    p.add_argument("--tdamp", type=float, default=100.0,
                   help="Nose-Hoover thermostat damping in fs.")
    p.add_argument("--timestep", type=float, default=1.0,
                   help="MD timestep in fs.")
    p.add_argument("--n-steps", type=int, default=1000,
                   help="Number of MD steps.")
    p.add_argument("--log-interval", type=int, default=100,
                   help="Log and trajectory write interval (in steps).")
    p.add_argument("--output", default="md.traj",
                   help="Output trajectory path.")
    p.add_argument("--logfile", default="md.log",
                   help="MD log path (energy/temperature per interval).")
    p.add_argument("--seed", type=int, default=None,
                   help="RNG seed for Maxwell-Boltzmann and Langevin "
                        "(reproducibility).")
    p.add_argument("--no-init-velocities", action="store_true",
                   help="Skip Maxwell-Boltzmann velocity init (use velocities "
                        "already on the input structure).")
    args = p.parse_args()

    from ase import units
    from ase.io import read
    from ase.io.trajectory import Trajectory
    from ase.md import MDLogger
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution

    atoms = read(args.structure)
    print(f"Loaded {len(atoms)} atoms from {args.structure}")
    atoms.calc = build_calculator(
        args.calculator, xtb_method=args.xtb_method,
        charge=args.charge, multiplicity=args.multiplicity,
        lj_epsilon=args.epsilon, lj_sigma=args.sigma, lj_rc=args.rc,
    )

    if not args.no_init_velocities:
        rng = None
        if args.seed is not None:
            import numpy as np
            rng = np.random.default_rng(args.seed)
        MaxwellBoltzmannDistribution(
            atoms, temperature_K=args.temperature, rng=rng,
        )

    dt = args.timestep * units.fs

    if args.ensemble == "nve":
        from ase.md.verlet import VelocityVerlet
        dyn = VelocityVerlet(atoms, timestep=dt)
    elif args.ensemble == "nvt-langevin":
        from ase.md.langevin import Langevin
        dyn = Langevin(
            atoms, timestep=dt,
            temperature_K=args.temperature,
            friction=args.friction / units.fs,
            rng=None,
        )
    elif args.ensemble == "nvt-nose-hoover":
        from ase.md.nose_hoover_chain import NoseHooverChainNVT
        dyn = NoseHooverChainNVT(
            atoms, timestep=dt,
            temperature_K=args.temperature,
            tdamp=args.tdamp * units.fs,
        )
    else:  # unreachable; argparse validates choices
        raise SystemExit(f"Unknown ensemble: {args.ensemble}")

    traj = Trajectory(args.output, "w", atoms)
    dyn.attach(traj.write, interval=args.log_interval)
    dyn.attach(
        MDLogger(dyn, atoms, args.logfile, header=True, stress=False,
                 peratom=True),
        interval=args.log_interval,
    )

    print(f"Calculator     : {args.calculator}"
          + (f" ({args.xtb_method})" if args.calculator == 'xtb' else ""))
    print(f"Ensemble       : {args.ensemble}")
    print(f"Timestep       : {args.timestep} fs")
    print(f"Steps          : {args.n_steps} "
          f"(= {args.n_steps * args.timestep / 1000:.2f} ps)")
    print(f"Log interval   : every {args.log_interval} steps")
    print(f"Output         : {args.output}, {args.logfile}")
    print()

    e0 = atoms.get_potential_energy()
    print(f"Initial PE     : {e0:.4f} eV")
    t_start = time.time()
    dyn.run(args.n_steps)
    t_elapsed = time.time() - t_start
    e1 = atoms.get_potential_energy()
    ke = atoms.get_kinetic_energy()
    n = len(atoms)
    T_inst = ke / (1.5 * n * units.kB) if n else 0.0

    print()
    print(f"Final PE       : {e1:.4f} eV")
    print(f"Final KE       : {ke:.4f} eV")
    print(f"Inst. T        : {T_inst:.1f} K (target {args.temperature} K)")
    print(f"Wall time      : {t_elapsed:.2f} s "
          f"({t_elapsed / args.n_steps * 1000:.2f} ms/step)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
