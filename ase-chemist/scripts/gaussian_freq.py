#!/usr/bin/env python3
"""Gaussian frequency analysis + thermochemistry.

When to use:
    The user wants vibrational frequencies, ZPE, enthalpy, and Gibbs
    free energy at DFT level. Inputs are a (typically tightly-)
    optimized geometry. Wraps ASE's Gaussian calculator with Freq in
    the route, runs g16/g09, and parses thermochem from the .log via
    an in-house parser (scripts/_gaussian_log.py) — no cclib dep.

When NOT to use:
    The geometry isn't tight enough (--convergence default in
    gaussian_opt.py). Spurious imaginary modes will appear; opt to
    --convergence tight or verytight first.
    Anharmonic corrections (Freq=Anharmonic) are out of scope for v1.4
    — they're expensive and need careful normal-mode follow-up.

Defaults policy (v1.4):
    No method/basis defaults — same as gaussian_sp.py and
    gaussian_opt.py. The freq method/basis MUST match the geometry's
    optimization method/basis — mixing produces garbage thermochem.

Examples:
    # Freq + thermochem at the same level used for the optimization
    python gaussian_freq.py --structure opt.xyz \\
        --method wB97XD --basis def2tzvp \\
        --charge 0 --multiplicity 1 \\
        --mem 8GB --nproc 8

    # Freq with implicit solvation (must match the SP / Opt solvation)
    python gaussian_freq.py --structure opt_aq.xyz \\
        --method "B3LYP EmpiricalDispersion=GD3BJ" --basis def2tzvp \\
        --charge 0 --multiplicity 1 --solvent water \\
        --mem 8GB --nproc 8

Output:
    Tagged key=value lines. Reports vibrational frequencies (cm^-1),
    ZPE (eV), enthalpy and Gibbs free energy (eV) at the requested
    temperature, and a [SUMMARY] line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gaussian_sp import (
    add_common_gaussian_args,
    detect_gaussian_binary,
)


HARTREE_EV = 27.211386245988


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Gaussian Freq + thermochemistry. Output parsed by the "
            "in-house _gaussian_log.py helper (no cclib dep). Reports "
            "vib_freqs, ZPE, enthalpy, Gibbs free energy."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_gaussian_args(p)
    p.add_argument("--temperature", type=float, default=298.15,
                   help="Thermochemistry temperature in K. Gaussian default "
                        "is 298.15 K; non-default T is set via "
                        "Temperature=N keyword on the route.")
    p.add_argument("--label", default="gaussian_freq",
                   help="Label for .com / .log files.")
    args = p.parse_args()

    from _gaussian_log import parse_thermochem
    from ase.calculators.gaussian import Gaussian
    from ase.io import read

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
    print(f"[INFO] temperature={args.temperature} K")

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
    # Add Freq + temperature to the route
    extra_route_parts = [f"Freq Temperature={args.temperature}"]
    if args.extra_route:
        extra_route_parts.append(args.extra_route)
    calc_kwargs["extra"] = " ".join(extra_route_parts)

    if args.solvent:
        if args.solvation_model == "smd":
            calc_kwargs["scrf"] = f"(SMD,Solvent={args.solvent})"
        else:
            calc_kwargs["scrf"] = f"(PCM,Solvent={args.solvent})"

    print(f"[INFO] Running Gaussian Freq job...")
    calc = Gaussian(**calc_kwargs)
    atoms.calc = calc
    energy = atoms.get_potential_energy()  # triggers the Freq run

    # Parse thermochem out of the .log via the in-house parser.
    log_path = Path(f"{args.label}.log")
    if not log_path.exists():
        raise SystemExit(f"Expected Gaussian log at {log_path}, not found.")
    thermo = parse_thermochem(log_path)

    vibfreqs = thermo.get("vib_freqs")
    if not vibfreqs:
        raise SystemExit(
            "Parsed the log but found no vibrational frequencies. "
            "Possible causes: (a) the Freq route keyword wasn't honored "
            "by Gaussian, (b) the input geometry was too far from a "
            "stationary point and the SCF failed, (c) the log uses an "
            "output format the in-house parser doesn't recognize "
            "(unusual — Gaussian's Freq output is normally stable). "
            f"Inspect {log_path} for diagnostics."
        )

    n_imag = thermo.get("n_imag", 0)

    print(f"[OK] electronic_energy_eV={energy:.6f}")
    print(f"[OK] n_vib_modes={len(vibfreqs)}")
    print(f"[OK] n_imag_modes={n_imag}")
    if n_imag > 0:
        imag = [f for f in vibfreqs if f < 0]
        print(f"[INFO] imaginary frequencies (cm^-1): "
              + ", ".join(f"{f:.1f}" for f in imag))
        print("[INFO] Imaginary modes mean the geometry is NOT at a true "
              "minimum. Tighten the optimization (--convergence tight or "
              "verytight in gaussian_opt.py) and re-run, or accept the "
              "thermochem with a clear caveat.")

    if "zpe_eV" in thermo:
        print(f"[OK] ZPE_eV={thermo['zpe_eV']:.4f}")
    if "enthalpy_eV" in thermo:
        print(f"[OK] enthalpy_H_eV={thermo['enthalpy_eV']:.6f}")
    if "gibbs_eV" in thermo:
        print(f"[OK] gibbs_G_eV={thermo['gibbs_eV']:.6f}")
    temperature = thermo.get("temperature_K", args.temperature)
    print(f"[OK] thermo_temperature_K={temperature:.2f}")

    gibbs_eV = thermo.get("gibbs_eV")
    print(f"[SUMMARY] Gaussian {args.method}/{args.basis} Freq: "
          f"{len(vibfreqs)} modes ({n_imag} imaginary), "
          + (f"G = {gibbs_eV:.4f} eV @ {temperature:.1f} K"
             if gibbs_eV is not None else
             "thermochem partial — see [OK] lines above")
          + ".")
    return 0 if n_imag == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
