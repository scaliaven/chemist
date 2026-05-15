#!/usr/bin/env python3
"""Single-point energy from an Amber prmtop.

When to use:
    Two modes:
      snapshot    one-shot energy on a single rst7 (imin=5, maxcyc=0).
                  Returns the decomposed energy terms (BOND, ANGLE,
                  DIHED, VDWAALS, EEL) the way pmemd reports them.
      trajectory  per-frame energies across a trajectory via cpptraj's
                  esander action. Writes cpptraj's raw per-frame
                  energy output to ``*_energies.dat``.

When NOT to use:
    Endpoint binding free energy — that needs three trajectories
    (complex / receptor / ligand) and goes through amber_score.py
    (MMPBSA.py).

Examples:
    # Snapshot SP on the heated rst7
    python amber_sp.py --mode snapshot --prmtop sys.prmtop \\
        --rst run/heat.rst7 --output-prefix heat_sp

    # Per-frame energies, every 10th frame
    python amber_sp.py --mode trajectory --prmtop sys.prmtop \\
        --trajectory run/prod.nc --frames "::10" \\
        --output-prefix prod_per_frame
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


def main_snapshot(args) -> int:
    prmtop = Path(args.prmtop).resolve()
    rst = Path(args.rst).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not prmtop.exists() or not rst.exists():
        raise SystemExit(f"prmtop or rst not found: {prmtop}, {rst}")

    engine = _amber.pick_engine(args.engine)
    prefix = args.output_prefix
    mdin = out_dir / f"{prefix}.in"
    mdout = out_dir / f"{prefix}.mdout"
    out_rst = out_dir / f"{prefix}.rst7"
    out_nc = out_dir / f"{prefix}.nc"

    mdin.write_text(
        "Single-point energy (imin=5, maxcyc=0)\n"
        "&cntrl\n"
        "  imin=5, maxcyc=0,\n"
        "  ntb=1, cut=10.0,\n"
        "  ntpr=1, ntwx=0,\n"
        "&end\n"
    )
    cmd = [engine, "-O", "-i", str(mdin), "-o", str(mdout),
           "-p", str(prmtop), "-c", str(rst),
           "-r", str(out_rst), "-x", str(out_nc)]
    rc = _amber.run_cmd(cmd)
    if rc != 0:
        raise SystemExit(f"{engine} SP failed (rc={rc}). Inspect {mdout}.")

    energies = _amber.parse_mdout(mdout)
    out_json = out_dir / f"{prefix}.json"
    out_json.write_text(json.dumps({
        "mode": "snapshot",
        "prmtop": str(prmtop),
        "rst": str(rst),
        "energy_kcal_per_mol": energies.get("EPTOT") or energies.get("ETOT"),
        "decomposition": {
            k: energies.get(k) for k in
            ("BOND", "ANGLE", "DIHED", "VDWAALS", "EEL", "EHBOND",
             "RESTRAINT", "VIRIAL", "EKCMT", "VOLUME", "DENSITY", "TEMP")
            if k in energies
        },
    }, indent=2) + "\n")
    print()
    print(f"[sp] wrote {out_json}")
    return 0


def main_trajectory(args) -> int:
    if shutil.which("cpptraj") is None:
        raise SystemExit(
            "cpptraj not on PATH — required for --mode trajectory."
        )
    prmtop = Path(args.prmtop).resolve()
    traj = Path(args.trajectory).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not prmtop.exists() or not traj.exists():
        raise SystemExit(f"prmtop or trajectory not found: {prmtop}, {traj}")

    prefix = args.output_prefix
    deck = out_dir / f"{prefix}.cpptraj"
    out_dat = out_dir / f"{prefix}_energies.dat"
    frames = args.frames or ""
    deck.write_text(
        f"parm {prmtop}\n"
        f"trajin {traj} {frames}\n"
        "autoimage\n"
        f"esander {prefix} out {out_dat}\n"
        "go\n"
        "quit\n"
    )
    rc = _amber.run_cmd(["cpptraj", "-i", str(deck)])
    if rc != 0:
        raise SystemExit(f"cpptraj failed (rc={rc}).")
    print()
    print(f"[sp] wrote {out_dat}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Single-point energy: snapshot mode (imin=5 via pmemd) or "
            "trajectory mode (per-frame via cpptraj esander)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", required=True, choices=["snapshot", "trajectory"])
    p.add_argument("--prmtop", required=True)
    p.add_argument("--rst", default=None,
                   help="Required when --mode snapshot.")
    p.add_argument("--trajectory", default=None,
                   help="Required when --mode trajectory.")
    p.add_argument("--frames", default=None,
                   help="cpptraj-style frame slice (e.g. '::10').")
    p.add_argument("--engine", default=None)
    p.add_argument("--output-prefix", default="sp")
    p.add_argument("--output-dir", default=".")
    args = p.parse_args()

    if args.mode == "snapshot":
        if not args.rst:
            raise SystemExit("--mode snapshot requires --rst.")
        return main_snapshot(args)
    if args.mode == "trajectory":
        if not args.trajectory:
            raise SystemExit("--mode trajectory requires --trajectory.")
        return main_trajectory(args)
    raise SystemExit(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main())
