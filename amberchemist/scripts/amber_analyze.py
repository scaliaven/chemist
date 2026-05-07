#!/usr/bin/env python3
"""cpptraj-driven trajectory analysis: RMSD / RMSF / RDF / hbond / radgyr.

Add-on script. Consumes the trajectory produced by amber_md.py /
amber_remd.py / amber_run.py and writes one CSV + one PNG per analysis.

When to use:
    The user has a finished .nc trajectory and a .prmtop and wants
    standard MD observables. Outputs match the shape of
    `ase-simulation/scripts/analyze_traj.py` so users get consistent
    file layouts across the two skills.

When NOT to use:
    For per-frame energy decomposition, use amber_sp.py --mode
    trajectory (cpptraj esander).
    For endpoint binding free energy, use amber_score.py.

REMD demux:
    --demux-remd --remd-dir <dir> consumes the output of amber_remd.py
    and writes per-temperature trajectories `demux_TXXX.nc` via
    cpptraj's `ensemble` keyword. Pair with --analyses to also run
    standard analyses on each demuxed trajectory.

Examples:
    python amber_analyze.py --prmtop sys.prmtop --trajectory prod.nc \\
        --analyses rmsd rmsf radgyr --output-dir analysis/

    python amber_analyze.py --prmtop sys.prmtop --trajectory prod.nc \\
        --analyses rdf --rdf-pair :WAT@O :LIG --rdf-rmax 8.0

    python amber_analyze.py --prmtop sys.prmtop --demux-remd \\
        --remd-dir remd_out/
"""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


def _require_cpptraj() -> None:
    if shutil.which("cpptraj") is None:
        raise SystemExit("cpptraj not on PATH — required for amber_analyze.py.")


def _read_dat(path: Path) -> tuple[list[str], list[list[float]]]:
    """Read cpptraj's `out file.dat` format: header + whitespace columns."""
    text = path.read_text()
    header: list[str] = []
    rows: list[list[float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            header = line.lstrip("#").split()
            continue
        parts = line.split()
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue
    return header, rows


def _plot_xy(out_png: Path, x, y, *, title: str, xlabel: str, ylabel: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def build_deck(args, deck_path: Path, dat_outputs: dict[str, Path]) -> None:
    """Render a cpptraj input deck for the requested analyses."""
    lines = [
        f"parm {Path(args.prmtop).resolve()}",
    ]
    if args.reference:
        lines.append(f"reference {Path(args.reference).resolve()}")
    lines.append(
        f"trajin {Path(args.trajectory).resolve()} 1 last {args.stride}"
    )
    lines.append("autoimage")
    if "rmsd" in args.analyses:
        ref_kw = "reference" if args.reference else "first"
        lines.append(
            f"rms {ref_kw} {args.rmsd_mask} out {dat_outputs['rmsd']}"
        )
    if "rmsf" in args.analyses:
        lines.append(
            f"atomicfluct out {dat_outputs['rmsf']} {args.rmsf_mask} byres"
        )
    if "rdf" in args.analyses:
        if not args.rdf_pair:
            raise SystemExit("rdf analysis needs --rdf-pair MASK1 MASK2.")
        m1, m2 = args.rdf_pair
        lines.append(
            f"rdf out {dat_outputs['rdf']} 0.1 {args.rdf_rmax} "
            f"{m1} {m2}"
        )
    if "radgyr" in args.analyses:
        lines.append(f"radgyr out {dat_outputs['radgyr']}")
    if "hbond" in args.analyses:
        d = args.hbond_donormask or "*"
        a = args.hbond_acceptormask or "*"
        lines.append(
            f"hbond donormask {d} acceptormask {a} out {dat_outputs['hbond']}"
        )
    lines += ["go", "quit"]
    deck_path.write_text("\n".join(lines) + "\n")


def run_demux(args) -> int:
    """Use cpptraj's `ensemble` keyword to demux a REMD ensemble."""
    remd_dir = Path(args.remd_dir).resolve()
    if not remd_dir.exists():
        raise SystemExit(f"--remd-dir not found: {remd_dir}")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prmtop = Path(args.prmtop).resolve()
    # Discover replicas
    replicas = sorted(remd_dir.glob("replica_*/prod.nc"))
    if not replicas:
        raise SystemExit(f"No replica_*/prod.nc found under {remd_dir}.")
    deck = out_dir / "demux.cpptraj"
    # cpptraj's ensemble syntax: trajin <first> <last> <stride> ensemble <list>
    others = " ".join(str(r) for r in replicas)
    deck.write_text(
        f"parm {prmtop}\n"
        f"ensemble {replicas[0]} {others}\n"
        "autoimage\n"
        f"trajout {out_dir}/demux.nc nobox\n"
        "run\n"
        "quit\n"
    )
    rc = _amber.run_cmd(["cpptraj", "-i", str(deck)])
    if rc != 0:
        raise SystemExit(f"cpptraj demux failed (rc={rc}).")
    print(f"[analyze] wrote demuxed trajectories under {out_dir}/")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "cpptraj-driven trajectory analysis: RMSD/RMSF/RDF/hbond/"
            "radgyr. Outputs CSV + PNG per analysis. Optional REMD demux."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--prmtop", required=True)
    p.add_argument("--trajectory", default=None,
                   help="Required unless --demux-remd is set.")
    p.add_argument("--reference", default=None,
                   help="Reference frame/structure (default = first frame).")
    p.add_argument("--analyses", nargs="+",
                   default=["rmsd", "rmsf"],
                   choices=["rmsd", "rmsf", "rdf", "hbond", "radgyr"])
    p.add_argument("--rmsd-mask", default="@CA,C,N|!@H=")
    p.add_argument("--rmsf-mask", default="@CA,C,N|!@H=")
    p.add_argument("--rdf-pair", nargs=2, metavar=("MASK1", "MASK2"))
    p.add_argument("--rdf-rmax", type=float, default=10.0)
    p.add_argument("--rdf-nbins", type=int, default=200)
    p.add_argument("--hbond-donormask", default=None)
    p.add_argument("--hbond-acceptormask", default=None)
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--demux-remd", action="store_true")
    p.add_argument("--remd-dir", default=None)
    p.add_argument("--output-prefix", default="analysis")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--keep-cpptraj-deck", action="store_true")
    args = p.parse_args()

    _require_cpptraj()
    if args.demux_remd:
        if not args.remd_dir:
            raise SystemExit("--demux-remd requires --remd-dir.")
        return run_demux(args)

    if not args.trajectory:
        raise SystemExit("--trajectory is required (or use --demux-remd).")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.output_prefix
    deck = out_dir / f"{prefix}.cpptraj"
    dat_outputs = {
        a: out_dir / f"{prefix}_{a}.dat"
        for a in args.analyses
    }
    build_deck(args, deck, dat_outputs)
    rc = _amber.run_cmd(["cpptraj", "-i", str(deck)])
    if rc != 0:
        raise SystemExit(f"cpptraj failed (rc={rc}).")

    # Convert each .dat to .csv + .png
    for a, dat in dat_outputs.items():
        if not dat.exists():
            print(f"[analyze] WARNING: {dat} not produced — skipping.")
            continue
        header, rows = _read_dat(dat)
        csv_path = out_dir / f"{prefix}_{a}.csv"
        with csv_path.open("w", newline="") as fh:
            w = csv.writer(fh)
            if header:
                w.writerow(header)
            w.writerows(rows)
        if rows and len(rows[0]) >= 2:
            x = [r[0] for r in rows]
            y = [r[1] for r in rows]
            png = out_dir / f"{prefix}_{a}.png"
            xlabel = header[0] if header else "frame"
            ylabel = header[1] if len(header) > 1 else a
            try:
                _plot_xy(png, x, y, title=a.upper(),
                         xlabel=xlabel, ylabel=ylabel)
                print(f"[analyze] wrote {csv_path}, {png}")
            except Exception as e:
                print(f"[analyze] plot failed for {a}: {e}")
        else:
            print(f"[analyze] wrote {csv_path}")

    if not args.keep_cpptraj_deck:
        try:
            deck.unlink()
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
