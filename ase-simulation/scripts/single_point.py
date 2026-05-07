#!/usr/bin/env python3
"""Single-point energy + electronic observables on a structure.

When to use:
    The user wants properties at a fixed geometry — total energy, dipole,
    Mulliken charges, HOMO-LUMO gap, bond orders. Common requests:
    "what's the energy of methanol?", "compute the HOMO-LUMO gap of
    benzene", "what are the Mulliken charges on this molecule?".

When NOT to use:
    If the geometry isn't yet relaxed, run `optimize.py` first — single-point
    properties on a strained geometry are usually nonsense. For trajectories
    of single-points (e.g., property evolution along MD), iterate inline.

HOMO-LUMO gap convention (READ THIS):
    This script reports the **raw eigenvalue gap** from tblite — i.e.,
    E(lowest unoccupied orbital) − E(highest occupied orbital), with no
    Fermi smearing or post-processing. For molecules with a minimal
    valence basis (notably small species like H2O, NH3, CH4 in GFN2-xTB),
    this raw gap can be much larger (60-100+ eV) than what the standalone
    `xtb` binary prints in its "HL-Gap" line (~10-15 eV). The xtb binary
    applies a different post-processing convention.

    The output below labels its number "HOMO-LUMO gap (raw eigenvalue)"
    so you can tell what convention you're looking at. If the user's
    expected value comes from the xtb binary, use that binary instead and
    parse its stdout — don't try to massage tblite's number to match.

    See `references/xtb.md` §"HOMO-LUMO: tblite vs the xtb binary".

Output:
    Tagged key=value lines, plus a [SUMMARY] line. Easy to grep.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HARTREE_EV = 27.211386245988


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Compute a single-point energy and (with xTB) electronic "
            "observables. Output is tagged key=value lines."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "HOMO-LUMO gap is the RAW EIGENVALUE gap from tblite — see the "
            "module docstring for why this can disagree with the xtb binary."
        ),
    )
    p.add_argument("--structure", required=True,
                   help="Input structure (xyz, cif, pdb, traj, ...).")
    p.add_argument("--calculator", required=True,
                   choices=["emt", "lj", "tip3p", "xtb"],
                   help="Backend. xtb = tblite GFN1/GFN2-xTB.")
    p.add_argument("--xtb-method", default="GFN2-xTB",
                   choices=["GFN1-xTB", "GFN2-xTB"])
    p.add_argument("--charge", type=int, default=0,
                   help="Net charge (xtb only).")
    p.add_argument("--multiplicity", type=int, default=1,
                   help="Spin multiplicity 2S+1 (xtb only).")
    p.add_argument("--frame", type=int, default=-1,
                   help="If structure is a trajectory, which frame.")
    args = p.parse_args()

    from ase.io import read

    atoms = read(args.structure, index=args.frame)
    n = len(atoms)
    print(f"[INFO] structure={args.structure} frame={args.frame} atoms={n}")
    print(f"[INFO] formula={atoms.get_chemical_formula()}")

    if args.calculator == "emt":
        from ase.calculators.emt import EMT
        atoms.calc = EMT()
    elif args.calculator == "lj":
        from ase.calculators.lj import LennardJones
        atoms.calc = LennardJones()
    elif args.calculator == "tip3p":
        from ase.calculators.tip3p import TIP3P
        atoms.calc = TIP3P()
    elif args.calculator == "xtb":
        try:
            from tblite.ase import TBLite
        except ImportError as e:
            raise SystemExit(
                f"tblite calculator unavailable: {e}\n"
                "Run scripts/check_env.py to diagnose. On HPC/conda systems "
                "prefer `conda install -c conda-forge tblite-python`."
            ) from e
        atoms.calc = TBLite(method=args.xtb_method, charge=args.charge,
                            multiplicity=args.multiplicity, verbosity=0)

    # Force evaluation populates calc.results
    energy = atoms.get_potential_energy()
    forces = atoms.get_forces()
    fmax = float((forces ** 2).sum(axis=1).max() ** 0.5)

    print(f"[OK] calculator={args.calculator}"
          + (f" method={args.xtb_method}" if args.calculator == "xtb" else ""))
    print(f"[OK] energy_eV={energy:.6f}")
    print(f"[OK] energy_eV_per_atom={energy / max(n, 1):.6f}")
    print(f"[OK] fmax_eV_per_A={fmax:.4f}")

    if args.calculator == "xtb":
        _xtb_extras(atoms, args)

    print(f"[SUMMARY] {args.calculator} single-point: "
          f"E = {energy:.4f} eV, fmax = {fmax:.3f} eV/Å"
          + (", HOMO-LUMO gap (raw) reported above" if args.calculator == "xtb"
             else ""))
    return 0


def _xtb_extras(atoms, args) -> None:
    """Print dipole, Mulliken charges, bond orders, and HOMO-LUMO from tblite."""
    import numpy as np

    # ASE-side results (populated by the force evaluation above)
    res = atoms.calc.results
    dipole = res.get("dipole")
    if dipole is not None:
        d = np.asarray(dipole)
        print(f"[OK] dipole_e_A=[{d[0]:.4f},{d[1]:.4f},{d[2]:.4f}] "
              f"|d|={float(np.linalg.norm(d)):.4f}")

    # Re-run via the tblite Calculator interface to get orbital data
    try:
        from tblite.interface import Calculator
        tb = Calculator(args.xtb_method, atoms.numbers, atoms.positions,
                        charge=args.charge,
                        uhf=args.multiplicity - 1)  # uhf = number of unpaired e-
        # silence the per-iteration SCC log
        try:
            tb.set("verbosity", 0)
        except Exception:
            pass
        tres = tb.singlepoint()
    except Exception as e:
        print(f"[INFO] orbital data unavailable: {type(e).__name__}: {e}")
        return

    # Mulliken charges
    charges = tres.get("charges")
    if charges is not None:
        sym = atoms.get_chemical_symbols()
        per_atom = ", ".join(f"{s}={c:+.3f}" for s, c in zip(sym, charges))
        print(f"[OK] mulliken_charges_e=[{per_atom}]")

    # Bond orders (matrix); print the upper-triangle entries above 0.1
    bo = tres.get("bond-orders")
    if bo is not None:
        sym = atoms.get_chemical_symbols()
        pairs = []
        for i in range(len(sym)):
            for j in range(i + 1, len(sym)):
                if bo[i, j] > 0.1:
                    pairs.append(f"{sym[i]}{i}-{sym[j]}{j}={bo[i, j]:.3f}")
        if pairs:
            print(f"[OK] wiberg_bond_orders=[{', '.join(pairs)}]")

    # HOMO-LUMO from raw eigenvalues
    eigs = tres.get("orbital-energies")
    occs = tres.get("orbital-occupations")
    if eigs is not None and occs is not None:
        eigs_ev = np.asarray(eigs) * HARTREE_EV
        occ_arr = np.asarray(occs)
        occupied = eigs_ev[occ_arr > 0.5]
        unoccupied = eigs_ev[occ_arr < 0.5]
        if len(occupied) > 0 and len(unoccupied) > 0:
            homo = float(occupied.max())
            lumo = float(unoccupied.min())
            gap = lumo - homo
            print(f"[OK] HOMO_eV={homo:.4f}")
            print(f"[OK] LUMO_eV={lumo:.4f}")
            print(f"[OK] HOMO_LUMO_gap_eV_raw={gap:.4f}")
            print(f"[INFO] HOMO-LUMO gap above is the RAW eigenvalue gap. "
                  f"The standalone xtb binary uses a different convention "
                  f"and may report a smaller value, especially for small "
                  f"molecules. See references/xtb.md.")


if __name__ == "__main__":
    raise SystemExit(main())
