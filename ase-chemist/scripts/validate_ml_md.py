#!/usr/bin/env python3
"""Cross-validate an ML-potential MD trajectory against a reference calculator.

When to use:
    Post-hoc validation on a saved .traj file produced by run_md.py with
    --calculator mace. Recomputes E and F at sampled frames through
    GFN2-xTB and reports MAE_E and MAE_F per frame, plus a single-line
    aggregate. Aborts (exit code 3) when MAE_F crosses the threshold so
    callers can spot the breach without parsing the CSV.

    run_md.py also performs in-process validation during the run; this
    standalone script exists for offline checking on completed runs and
    for reproducing the same numbers from a different reference.

Examples:
    # Validate an organic-system MACE trajectory against GFN2-xTB
    python validate_ml_md.py --trajectory md.traj --reference xtb \\
        --output validation.csv

    # Validate every 10th frame, abort threshold 50 meV/A
    python validate_ml_md.py --trajectory md.traj --reference xtb \\
        --stride 10 --abort-mae-f 50.0
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional


class ValidationFailed(RuntimeError):
    """Raised when MAE_F crosses the abort threshold during MD validation."""

    def __init__(self, frame: int, mae_f_mev: float, threshold_mev: float):
        self.frame = frame
        self.mae_f_mev = mae_f_mev
        self.threshold_mev = threshold_mev
        super().__init__(
            f"frame {frame}: MAE_F = {mae_f_mev:.2f} meV/A exceeds "
            f"threshold {threshold_mev:.2f} meV/A"
        )


def build_reference_calculator(name: str, *, xtb_method: str = "GFN2-xTB",
                               charge: int = 0, multiplicity: int = 1):
    if name == "xtb":
        try:
            from tblite.ase import TBLite
        except ImportError as e:
            raise SystemExit(
                f"tblite is not installed: {e}\n"
                "Install with: conda install -c conda-forge tblite-python\n"
                "Run scripts/check_env.py to see the broader status."
            ) from e
        return TBLite(method=xtb_method, charge=charge,
                      multiplicity=multiplicity, verbosity=0)
    raise SystemExit(
        f"Unknown reference calculator: {name}. v2.1 ships only --reference xtb."
    )


def validate_frame(atoms, reference_calc) -> tuple[float, float, float]:
    """Recompute E/F with reference, compare to atoms.calc results.

    Returns (mae_e_mev, mae_f_mev_per_A, max_F_dev_mev_per_A).

    Requires `atoms` to already have computed energies/forces on its
    current calculator (e.g. inside an MD step).
    """
    import numpy as np

    ml_e = atoms.get_potential_energy()
    ml_f = atoms.get_forces()

    ref_atoms = atoms.copy()
    ref_atoms.calc = reference_calc
    ref_e = ref_atoms.get_potential_energy()
    ref_f = ref_atoms.get_forces()

    mae_e_mev = abs(ml_e - ref_e) * 1000.0
    f_diff = ml_f - ref_f
    mae_f_mev = float(np.mean(np.linalg.norm(f_diff, axis=1))) * 1000.0
    max_f_mev = float(np.max(np.linalg.norm(f_diff, axis=1))) * 1000.0
    return mae_e_mev, mae_f_mev, max_f_mev


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Cross-validate an ML-potential MD trajectory against a "
            "reference (GFN2-xTB by default). Writes per-frame MAE_E and "
            "MAE_F to a CSV; exits 3 on threshold breach."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--trajectory", required=True,
                   help="Trajectory to validate (.traj with energies/forces).")
    p.add_argument("--reference", default="xtb", choices=["xtb"],
                   help="Reference calculator. xtb = GFN2-xTB via tblite.")
    p.add_argument("--xtb-method", default="GFN2-xTB",
                   choices=["GFN1-xTB", "GFN2-xTB"])
    p.add_argument("--charge", type=int, default=0)
    p.add_argument("--multiplicity", type=int, default=1)
    p.add_argument("--stride", type=int, default=1,
                   help="Validate every Nth frame.")
    p.add_argument("--abort-mae-f", type=float, default=100.0,
                   help=(
                       "Abort threshold for force MAE in meV/A. "
                       "Returns exit code 3 when breached."
                   ))
    p.add_argument("--output", default="validation.csv",
                   help="Output CSV path.")
    args = p.parse_args()

    from ase.io.trajectory import Trajectory

    traj = Trajectory(args.trajectory, "r")
    print(f"Loaded {len(traj)} frames from {args.trajectory}")

    ref = build_reference_calculator(
        args.reference, xtb_method=args.xtb_method,
        charge=args.charge, multiplicity=args.multiplicity,
    )

    out_path = Path(args.output)
    breach: Optional[ValidationFailed] = None

    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "frame", "MAE_E_meV", "MAE_F_meV_per_A", "max_F_dev_meV_per_A",
        ])

        for i, atoms in enumerate(traj):
            if i % args.stride != 0:
                continue
            try:
                mae_e, mae_f, max_f = validate_frame(atoms, ref)
            except Exception as e:
                print(f"[validate] frame {i}: error ({e}); skipping.")
                continue

            writer.writerow([
                i, f"{mae_e:.3f}", f"{mae_f:.3f}", f"{max_f:.3f}",
            ])
            fh.flush()

            print(
                f"[validate] frame {i:5d}: "
                f"|dE| = {mae_e:7.2f} meV   "
                f"MAE_F = {mae_f:6.2f} meV/A   "
                f"max |dF| = {max_f:6.2f} meV/A"
            )

            if mae_f > args.abort_mae_f:
                breach = ValidationFailed(i, mae_f, args.abort_mae_f)
                print(
                    f"[validate] ABORT: {breach}. Trust the trajectory "
                    f"only up to frame {max(0, i - args.stride)}."
                )
                break

    print(f"Wrote {out_path}")
    return 3 if breach is not None else 0


__all__ = [
    "ValidationFailed",
    "build_reference_calculator",
    "validate_frame",
]


if __name__ == "__main__":
    raise SystemExit(main())
