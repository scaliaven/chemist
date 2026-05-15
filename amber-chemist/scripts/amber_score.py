#!/usr/bin/env python3
"""MMPBSA / MMGBSA endpoint binding free energy via MMPBSA.py.

When to use:
    The user has a finished trajectory of a protein-ligand complex
    (or any multi-component system) plus the three prmtops (complex,
    receptor, ligand) and wants an endpoint binding free energy
    estimate. Optionally per-residue decomposition or a computational
    alanine scan.

When NOT to use:
    Rigorous free energy (TI / FEP / MBAR) — endpoint MMPBSA is an
    approximate scoring method, not a free-energy method. See
    references/scoring.md §"What MMPBSA is not."
    Per-frame energy decomposition without binding context — that's
    amber_sp.py --mode trajectory (cpptraj esander).

Examples:
    # GB only, MPI x4
    python amber_score.py --complex-prmtop com.prmtop \\
        --receptor-prmtop rec.prmtop --ligand-prmtop lig.prmtop \\
        --trajectory prod.nc --method gb --mpi 4 \\
        --output-dir mmpbsa/

    # Alanine scan + per-residue decomp
    python amber_score.py --complex-prmtop com.prmtop \\
        --receptor-prmtop rec.prmtop --ligand-prmtop lig.prmtop \\
        --trajectory prod.nc --method gb \\
        --alanine-scan --per-residue --output-dir mmpbsa/

Output:
    <prefix>.in                   — MMPBSA input deck
    FINAL_RESULTS_MMPBSA.dat      — MMPBSA.py output (preserved)
    <prefix>_summary.json         — parsed delta-G summary
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


def _render_deck(args) -> str:
    sections = [
        "&general",
        f"  startframe={args.start_frame}, "
        + (f"endframe={args.end_frame}, " if args.end_frame is not None else "")
        + f"interval={args.stride}, keep_files={int(args.keep_files)},",
        "/",
    ]
    if args.method in ("gb", "both"):
        sections += [
            "&gb",
            f"  igb={args.gb_model}, saltcon={args.ionic_strength},",
            "/",
        ]
    if args.method in ("pb", "both"):
        sections += [
            "&pb",
            f"  istrng={args.ionic_strength}, radiopt=0, "
            f"inp=1,",
            "/",
        ]
    if args.per_residue:
        sections += [
            "&decomp",
            "  idecomp=2, dec_verbose=1,",
            "/",
        ]
    if args.alanine_scan:
        sections += [
            "&alanine_scanning",
            "/",
        ]
    return "MMPBSA endpoint scoring (amber_score.py)\n" + "\n".join(sections) + "\n"


_FINAL_DG_RE = re.compile(
    r"DELTA TOTAL\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)"
)


def _parse_results(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(errors="replace")
    out: dict = {}
    m = _FINAL_DG_RE.search(text)
    if m:
        out["delta_total_kcal_per_mol"] = float(m.group(1))
        out["std_dev"] = float(m.group(2))
        out["std_err_mean"] = float(m.group(3))
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "MMPBSA / MMGBSA endpoint binding free energy via MMPBSA.py."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--complex-prmtop", required=True)
    p.add_argument("--receptor-prmtop", required=True)
    p.add_argument("--ligand-prmtop", required=True)
    p.add_argument("--trajectory", required=True)
    p.add_argument("--solvated-prmtop", default=None,
                   help="If set, MMPBSA.py strips waters per-frame using "
                        "this prmtop (-sp).")
    p.add_argument("--method", default="gb", choices=["gb", "pb", "both"])
    p.add_argument("--gb-model", type=int, default=2,
                   help="igb value (default 2 = OBC2 / GBneck2-class).")
    p.add_argument("--ionic-strength", type=float, default=0.150)
    p.add_argument("--start-frame", type=int, default=1)
    p.add_argument("--end-frame", type=int, default=0,
                   help="0 = last frame (cpptraj convention).")
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--per-residue", action="store_true")
    p.add_argument("--alanine-scan", action="store_true")
    p.add_argument("--mpi", type=int, default=1,
                   help="If > 1, uses MMPBSA.py.MPI.")
    p.add_argument("--keep-files", action="store_true")
    p.add_argument("--output-prefix", default="mmpbsa")
    p.add_argument("--output-dir", default=".")
    args = p.parse_args()

    binary = "MMPBSA.py.MPI" if args.mpi > 1 else "MMPBSA.py"
    if shutil.which(binary) is None:
        raise SystemExit(
            f"{binary} not on PATH. amber_score.py hard-fails without "
            "MMPBSA.py. Install AmberTools or check `python "
            "scripts/check_env.py`."
        )

    com = Path(args.complex_prmtop).resolve()
    rec = Path(args.receptor_prmtop).resolve()
    lig = Path(args.ligand_prmtop).resolve()
    traj = Path(args.trajectory).resolve()
    for f in (com, rec, lig, traj):
        if not f.exists():
            raise SystemExit(f"file not found: {f}")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    deck = out_dir / f"{args.output_prefix}.in"
    deck.write_text(_render_deck(args))

    cmd = [binary, "-O", "-i", str(deck),
           "-cp", str(com), "-rp", str(rec), "-lp", str(lig),
           "-y", str(traj)]
    if args.solvated_prmtop:
        cmd += ["-sp", str(Path(args.solvated_prmtop).resolve())]
    if args.mpi > 1:
        cmd = ["mpirun", "-np", str(args.mpi)] + cmd

    rc = _amber.run_cmd(cmd, cwd=out_dir)
    if rc != 0:
        raise SystemExit(f"MMPBSA failed (rc={rc}).")

    results = _parse_results(out_dir / "FINAL_RESULTS_MMPBSA.dat")
    summary = {
        "method": args.method,
        "gb_model": args.gb_model if args.method in ("gb", "both") else None,
        "ionic_strength": args.ionic_strength,
        "alanine_scan": args.alanine_scan,
        "per_residue": args.per_residue,
        "n_frames_stride": args.stride,
        **results,
    }
    summary_path = out_dir / f"{args.output_prefix}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print()
    print(f"[score] wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
