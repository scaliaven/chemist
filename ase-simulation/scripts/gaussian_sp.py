#!/usr/bin/env python3
"""Gaussian DFT single-point energy + (optional) electronic observables.

When to use:
    The user explicitly wants DFT-quality numbers — publication
    thermochemistry, transition-metal systems where xTB is unreliable,
    reaction-energy benchmarks within ~few-kcal/mol. Wraps ASE's
    Gaussian calculator: writes a .com, runs g16 (or g09 fallback),
    parses E/F/dipole via ASE.

When NOT to use:
    Most organic single-points where xTB-quality is enough — use
    `single_point.py --calculator xtb`. Use this only when DFT is
    actually needed; Gaussian jobs cost minutes-to-hours, xTB costs
    seconds.

Defaults policy (v1.4):
    No method/basis defaults. The user MUST pass --method and --basis.
    Picking silently is the wrong-physics failure mode v1 already
    guards against (B3LYP/6-31G(d) is fine for thermochem of small
    organics but a terrible choice for transition metals; ωB97X-D
    is better for organics but slower; etc.). Common reasonable
    choices documented in references/gaussian.md §1.

    Resource flags --mem and --nproc are also required: psutil
    detection misreads NUMA / cgroups / shared queue nodes, so the
    skill does not auto-pick.

Solvation:
    --solvent <name> turns on implicit solvation; default model is
    SMD (~3-5 kcal/mol RMSD better than IEF-PCM on aqueous
    solvation free energies, per SAMPL benchmarks). Override with
    --solvation-model pcm if reproducing older literature.

Examples:
    # DFT single-point, ωB97X-D / def2-TZVP, gas phase
    python gaussian_sp.py --structure mol.xyz \\
        --method wB97XD --basis def2tzvp \\
        --charge 0 --multiplicity 1 \\
        --mem 8GB --nproc 8

    # Aqueous-phase single-point with SMD (water)
    python gaussian_sp.py --structure mol.xyz \\
        --method "B3LYP EmpiricalDispersion=GD3BJ" --basis def2tzvp \\
        --charge 0 --multiplicity 1 \\
        --solvent water \\
        --mem 8GB --nproc 8

Output:
    Tagged key=value lines and a [SUMMARY] line. Easy to grep.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


HARTREE_EV = 27.211386245988


def detect_gaussian_binary(prefer: str | None = None) -> str:
    """Pick g16 if available, else g09. Raise if neither is on PATH."""
    if prefer is not None:
        path = shutil.which(prefer)
        if path is None:
            raise SystemExit(
                f"--gaussian-binary {prefer} not on PATH. Drop the flag "
                f"to auto-select (g16 > g09)."
            )
        return prefer
    for candidate in ("g16", "g09"):
        if shutil.which(candidate):
            return candidate
    raise SystemExit(
        "No Gaussian binary on PATH (need g16 or g09). "
        "Run scripts/check_env.py for detection details."
    )


def build_gaussian_calc(args, label: str, properties: list[str]):
    """Construct ase.calculators.gaussian.Gaussian with the requested route."""
    from ase.calculators.gaussian import Gaussian

    binary = detect_gaussian_binary(args.gaussian_binary)
    calc_kwargs: dict = {
        "label": label,
        "command": f"{binary} < PREFIX.com > PREFIX.log",
        "method": args.method,
        "basis": args.basis,
        "charge": args.charge,
        "mult": args.multiplicity,
        "mem": args.mem,
        "nprocshared": str(args.nproc),
    }
    if args.solvent:
        if args.solvation_model == "smd":
            calc_kwargs["scrf"] = f"(SMD,Solvent={args.solvent})"
        else:  # pcm
            calc_kwargs["scrf"] = f"(PCM,Solvent={args.solvent})"
    if args.extra_route:
        calc_kwargs["extra"] = args.extra_route
    if "forces" in properties:
        # request the analytical gradient
        calc_kwargs["force"] = ""
    return Gaussian(**calc_kwargs), binary


def add_common_gaussian_args(p: argparse.ArgumentParser) -> None:
    """Shared CLI for gaussian_sp / gaussian_opt / gaussian_freq."""
    p.add_argument("--structure", required=True,
                   help="Input structure (xyz, cif, pdb, traj, ...).")
    p.add_argument("--method", required=True,
                   help="DFT method or correlated method, e.g. wB97XD, "
                        "B3LYP, M06-2X, MP2, CCSD(T). No default — "
                        "the right choice depends on the system.")
    p.add_argument("--basis", required=True,
                   help="Basis set, e.g. def2tzvp, 6-31G(d), aug-cc-pVTZ. "
                        "No default.")
    p.add_argument("--charge", type=int, required=True,
                   help="Net charge.")
    p.add_argument("--multiplicity", type=int, required=True,
                   help="Spin multiplicity (2S+1). 1 = closed-shell singlet, "
                        "2 = doublet (radical), etc. Wrong multiplicity "
                        "silently produces a converged-but-wrong wavefunction.")
    p.add_argument("--solvent", default=None,
                   help="Solvent name for SCRF (e.g. water, acetonitrile). "
                        "Default: gas phase.")
    p.add_argument("--solvation-model", default="smd",
                   choices=["smd", "pcm"],
                   help="SCRF solvation model. SMD outperforms IEF-PCM "
                        "by ~3-5 kcal/mol RMSD on aqueous solvation free "
                        "energies; PCM kept for older-literature matching.")
    p.add_argument("--mem", required=True,
                   help="Gaussian %%mem value, e.g. 8GB, 32GB. Required: "
                        "psutil detection misreads NUMA / cgroups / "
                        "shared queue nodes.")
    p.add_argument("--nproc", type=int, required=True,
                   help="Gaussian %%nprocshared value. Required for the "
                        "same reason as --mem.")
    p.add_argument("--extra-route", default=None,
                   help="Extra route-line tokens passed verbatim "
                        "(e.g. \"Pop=Mulliken Int=UltraFine\"). "
                        "Use only when the standard kwargs don't expose "
                        "what you need.")
    p.add_argument("--gaussian-binary", default=None,
                   choices=["g16", "g09"],
                   help="Override binary auto-selection (default: g16 > g09).")


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Gaussian DFT single-point energy / forces / dipole. "
            "Wraps ase.calculators.gaussian.Gaussian; output is "
            "tagged key=value."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_gaussian_args(p)
    p.add_argument("--frame", type=int, default=-1,
                   help="If --structure is a trajectory, which frame.")
    p.add_argument("--label", default="gaussian_sp",
                   help="Label for .com / .log files.")
    args = p.parse_args()

    from ase.io import read

    atoms = read(args.structure, index=args.frame)
    n = len(atoms)
    print(f"[INFO] structure={args.structure} frame={args.frame} atoms={n}")
    print(f"[INFO] formula={atoms.get_chemical_formula()}")
    print(f"[INFO] method={args.method} basis={args.basis} "
          f"charge={args.charge} mult={args.multiplicity}")
    if args.solvent:
        print(f"[INFO] solvation={args.solvation_model.upper()} "
              f"solvent={args.solvent}")
    print(f"[INFO] resources: mem={args.mem} nproc={args.nproc}")

    calc, binary = build_gaussian_calc(
        args, label=args.label, properties=["energy", "forces"],
    )
    print(f"[INFO] gaussian-binary={binary}")
    atoms.calc = calc

    energy = atoms.get_potential_energy()
    forces = atoms.get_forces()
    fmax = float((forces ** 2).sum(axis=1).max() ** 0.5)

    print(f"[OK] energy_eV={energy:.6f}")
    print(f"[OK] energy_eV_per_atom={energy / max(n, 1):.6f}")
    print(f"[OK] fmax_eV_per_A={fmax:.4f}")

    dipole = atoms.calc.results.get("dipole")
    if dipole is not None:
        import numpy as np
        d = np.asarray(dipole)
        print(f"[OK] dipole_e_A=[{d[0]:.4f},{d[1]:.4f},{d[2]:.4f}] "
              f"|d|={float(np.linalg.norm(d)):.4f}")

    # Optional cclib parse for richer observables (charges, MO eigenvalues).
    try:
        import cclib
        log_path = Path(f"{args.label}.log")
        if log_path.exists():
            data = cclib.io.ccopen(str(log_path)).parse()
            mocoeffs_n = getattr(data, "nmo", None)
            homos = getattr(data, "homos", None)
            moenergies = getattr(data, "moenergies", None)
            if homos is not None and moenergies is not None:
                # moenergies is a list per spin; use spin 0
                mo = moenergies[0]
                ihomo = int(homos[0])
                if 0 <= ihomo < len(mo) - 1:
                    homo_eV = float(mo[ihomo])
                    lumo_eV = float(mo[ihomo + 1])
                    print(f"[OK] HOMO_eV={homo_eV:.4f}")
                    print(f"[OK] LUMO_eV={lumo_eV:.4f}")
                    print(f"[OK] HOMO_LUMO_gap_eV={lumo_eV - homo_eV:.4f}")
            atomcharges = getattr(data, "atomcharges", None)
            if atomcharges:
                # atomcharges is a dict like {"mulliken": [...], ...}
                for scheme, charges in atomcharges.items():
                    sym = atoms.get_chemical_symbols()
                    per_atom = ", ".join(
                        f"{s}={c:+.3f}" for s, c in zip(sym, charges)
                    )
                    print(f"[OK] {scheme}_charges_e=[{per_atom}]")
    except ImportError:
        print("[INFO] cclib not installed; skipping richer observables. "
              "Install with: pip install cclib")
    except Exception as e:
        print(f"[INFO] cclib parse failed ({type(e).__name__}: {e}); "
              "energy/forces/dipole still valid above.")

    print(f"[SUMMARY] Gaussian {args.method}/{args.basis} single-point: "
          f"E = {energy:.4f} eV, fmax = {fmax:.3f} eV/Å"
          + (f", solvation={args.solvation_model.upper()}({args.solvent})"
             if args.solvent else ", gas phase"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
