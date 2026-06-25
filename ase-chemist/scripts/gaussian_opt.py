#!/usr/bin/env python3
"""Gaussian DFT geometry optimization via Gaussian's L103 optimizer.

When to use:
    The user wants a DFT-quality optimized geometry — for input to a
    subsequent Freq job, for publication structures, for transition
    metals where xTB underperforms. Wraps `GaussianOptimizer` from ASE,
    which delegates to Gaussian's internal L103 optimizer (much faster
    than wrapping ASE's BFGS around per-step Gaussian SP calls).

When NOT to use:
    Organic systems where xTB is enough — use `optimize.py --calculator
    xtb`. Transition-state searches — Opt=TS needs a good Hessian guess
    and IRC verification; v1.4 does not provide that wrapper, push to
    v3+. Constrained / NEB optimization — use ASE inline.

Defaults policy (v1.4):
    No method/basis defaults — same as gaussian_sp.py. See
    references/gaussian_method_selection.md for the recommended choices.

Convergence flag:
    GaussianOptimizer's `fmax` is a STRING ('loose' / 'default' /
    'tight' / 'verytight'), not a numeric eV/Å threshold like ASE
    optimizers. The values map onto Gaussian's Opt=... options. Use
    'tight' or 'verytight' if the optimized geometry feeds into a
    Freq job.

Examples:
    # Tight DFT optimization for downstream Freq
    python gaussian_opt.py --structure mol.xyz \\
        --method wB97XD --basis def2tzvp \\
        --charge 0 --multiplicity 1 \\
        --convergence tight \\
        --mem 8GB --nproc 8 \\
        --output opt.xyz

    # Aqueous-phase optimization with SMD (water)
    python gaussian_opt.py --structure mol.xyz \\
        --method "B3LYP EmpiricalDispersion=GD3BJ" --basis def2tzvp \\
        --charge 0 --multiplicity 1 \\
        --solvent water \\
        --mem 8GB --nproc 8 \\
        --output opt_aq.xyz

Output:
    The optimized geometry written to --output (default opt.xyz).
    Tagged key=value diagnostics on stdout, plus a [SUMMARY] line.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from gaussian_sp import (  # local import; same scripts/ directory
    add_common_gaussian_args,
    detect_gaussian_binary,
    scrf_kwarg,
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Gaussian DFT geometry optimization via L103. Uses ASE's "
            "GaussianOptimizer, which delegates to Gaussian's internal "
            "optimizer (one g16/g09 invocation for the whole opt)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_gaussian_args(p)
    p.add_argument("--convergence", default="default",
                   choices=["loose", "default", "tight", "verytight"],
                   help="Gaussian Opt convergence flag (string, NOT eV/Å). "
                        "Use 'tight' for Freq-input geometries.")
    p.add_argument("--max-cycles", type=int, default=200,
                   help="Maximum optimizer cycles (Gaussian Opt=maxcycle=N).")
    p.add_argument("--output", default="opt.xyz",
                   help="Optimized geometry output (extension determines "
                        "format).")
    p.add_argument("--label", default="gaussian_opt",
                   help="Label for .com / .log files.")
    args = p.parse_args()

    from ase.calculators.gaussian import Gaussian, GaussianOptimizer
    from ase.io import read, write

    atoms = read(args.structure)
    n = len(atoms)
    print(f"[INFO] structure={args.structure} atoms={n} "
          f"formula={atoms.get_chemical_formula()}")
    print(f"[INFO] method={args.method} basis={args.basis} "
          f"charge={args.charge} mult={args.multiplicity}")
    if args.solvent:
        print(f"[INFO] solvation={args.solvation_model.upper()} "
              f"solvent={args.solvent}")
    print(f"[INFO] resources: mem={args.mem} nproc={args.nproc}")
    print(f"[INFO] convergence={args.convergence} max_cycles={args.max_cycles}")

    binary = detect_gaussian_binary(args.gaussian_binary)
    print(f"[INFO] gaussian-binary={binary}")

    calc_kwargs: dict = {
        "label": args.label,
        "command": f"{binary} < PREFIX.com > PREFIX.log",
        "method": args.method,
        "basis": args.basis,
        "charge": args.charge,
        "mult": args.multiplicity,
        "mem": args.mem,
        "nprocshared": str(args.nproc),
    }
    scrf = scrf_kwarg(args.solvation_model, args.solvent)
    if scrf:
        calc_kwargs["scrf"] = scrf
    if args.extra_route:
        calc_kwargs["extra"] = args.extra_route

    calc = Gaussian(**calc_kwargs)

    e0 = None  # Gaussian internal opt won't expose initial E without an SP
    print(f"[INFO] Running Gaussian internal optimizer "
          f"(Opt={args.convergence}, maxcycle={args.max_cycles})...")
    opt = GaussianOptimizer(atoms, calc)
    opt.run(fmax=args.convergence, steps=args.max_cycles)

    # After GaussianOptimizer returns, atoms holds the optimized geometry
    # and atoms.calc.results has the final energy/forces (parsed from .log).
    e1 = atoms.get_potential_energy()
    forces = atoms.get_forces()
    fmax = float((forces ** 2).sum(axis=1).max() ** 0.5)

    write(args.output, atoms)

    print(f"[OK] final_energy_eV={e1:.6f}")
    print(f"[OK] final_fmax_eV_per_A={fmax:.4f}")
    print(f"[OK] output={args.output}")
    print(f"[SUMMARY] Gaussian {args.method}/{args.basis} optimization "
          f"converged at {args.convergence}: "
          f"E = {e1:.4f} eV, fmax = {fmax:.3f} eV/Å. Wrote {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
