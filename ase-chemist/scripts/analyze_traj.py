#!/usr/bin/env python3
"""Compute RMSD, RMSF, energy drift, and (optionally) RDF from a trajectory.

When to use:
    The user has a .traj or .xyz file and wants standard observables —
    "did this simulation equilibrate?", "show me the RMSD", "is the water
    structured?". This script writes both PNG plots and CSV data so the user
    can replot without rerunning.

When NOT to use:
    For protein-specific analyses (per-residue RMSF with chain selection,
    secondary structure, contact maps), use MDAnalysis directly with its
    selection language. See references/analysis.md for the patterns.

Outputs (next to the trajectory):
    rmsd.png, rmsd.csv          — RMSD vs frame, after Kabsch alignment
    rmsf.png, rmsf.csv          — Per-atom fluctuation
    energy.png, energy.csv      — PE / KE / total energy and drift
    rdf.png, rdf.csv            — Only if --rdf-elements is given

Examples:
    python analyze_traj.py --trajectory md.traj
    python analyze_traj.py --trajectory md.traj --rdf-elements O O --rdf-rmax 6.0
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np


def kabsch_align(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """Return P aligned (rotated+translated) onto Q using the Kabsch algorithm."""
    Pc = P - P.mean(0)
    Qc = Q - Q.mean(0)
    H = Pc.T @ Qc
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return Pc @ R.T + Q.mean(0)


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Standard analyses on an ASE trajectory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--trajectory", required=True,
                   help="Path to .traj or .xyz file.")
    p.add_argument("--reference-frame", type=int, default=0,
                   help="Frame index used as the RMSD reference.")
    p.add_argument("--no-align", action="store_true",
                   help="Skip Kabsch alignment before RMSD/RMSF "
                        "(only do this if frames are already aligned).")
    p.add_argument("--rdf-elements", nargs=2, metavar=("E1", "E2"),
                   help="If given, compute g(r) between these elements "
                        "(e.g. --rdf-elements O O).")
    p.add_argument("--rdf-rmax", type=float, default=6.0,
                   help="Maximum r for RDF in Å.")
    p.add_argument("--rdf-nbins", type=int, default=200,
                   help="Number of RDF histogram bins.")
    p.add_argument("--output-dir", default=None,
                   help="Where to put outputs (default: alongside trajectory).")
    args = p.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit(
            "matplotlib is required. Run `pip install matplotlib`."
        )

    from ase.io import read

    traj_path = Path(args.trajectory)
    out_dir = Path(args.output_dir) if args.output_dir else traj_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {traj_path} ...")
    frames = read(str(traj_path), index=":")
    if not isinstance(frames, list):
        frames = [frames]
    n_frames = len(frames)
    n_atoms = len(frames[0])
    print(f"  {n_frames} frames, {n_atoms} atoms")

    if n_frames < 2:
        print("Trajectory has fewer than 2 frames; skipping time-series analyses.")
        return 0
    if not (-n_frames <= args.reference_frame < n_frames):
        raise SystemExit(
            f"--reference-frame {args.reference_frame} out of range for "
            f"{n_frames} frames."
        )

    # --- Stack positions
    positions = np.stack([f.positions for f in frames])  # (T, N, 3)
    ref = positions[args.reference_frame]

    # --- RMSD
    print("Computing RMSD ...")
    rmsd = np.zeros(n_frames)
    aligned_positions = positions.copy()
    for i, P in enumerate(positions):
        aligned = P if args.no_align else kabsch_align(P, ref)
        aligned_positions[i] = aligned
        rmsd[i] = np.sqrt(((aligned - ref) ** 2).sum(-1).mean())

    write_csv(out_dir / "rmsd.csv",
              ["frame", "rmsd_angstrom"],
              [[i, float(r)] for i, r in enumerate(rmsd)])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(rmsd)
    ax.set_xlabel("Frame")
    ax.set_ylabel(f"RMSD vs frame {args.reference_frame} (Å)")
    ax.set_title(f"RMSD ({n_frames} frames, {n_atoms} atoms)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "rmsd.png", dpi=150)
    plt.close(fig)
    print(f"  -> {out_dir / 'rmsd.png'}, {out_dir / 'rmsd.csv'}")

    # --- RMSF
    print("Computing RMSF ...")
    mean_pos = aligned_positions.mean(axis=0)
    rmsf = np.sqrt(((aligned_positions - mean_pos) ** 2).sum(-1).mean(axis=0))
    symbols = frames[0].get_chemical_symbols()
    write_csv(out_dir / "rmsf.csv",
              ["atom_index", "element", "rmsf_angstrom"],
              [[i, s, float(r)] for i, (s, r) in enumerate(zip(symbols, rmsf))])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(np.arange(n_atoms), rmsf)
    ax.set_xlabel("Atom index")
    ax.set_ylabel("RMSF (Å)")
    ax.set_title("Per-atom fluctuation")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "rmsf.png", dpi=150)
    plt.close(fig)
    print(f"  -> {out_dir / 'rmsf.png'}, {out_dir / 'rmsf.csv'}")

    # --- Energy drift
    print("Computing energy drift ...")
    pe = np.array([_safe_get(f, "get_potential_energy") for f in frames])
    ke = np.array([_safe_get(f, "get_kinetic_energy") for f in frames])
    if np.all(np.isnan(pe)):
        print("  no potential energies stored in trajectory; skipping.")
    else:
        total = pe + ke
        drift_meV = 1000.0 * (total - total[0]) / n_atoms
        write_csv(out_dir / "energy.csv",
                  ["frame", "PE_eV", "KE_eV", "Etot_eV",
                   "drift_meV_per_atom"],
                  [[i, float(p_), float(k_), float(p_ + k_), float(d_)]
                   for i, (p_, k_, d_) in enumerate(zip(pe, ke, drift_meV))])

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(pe, label="PE (eV)")
        ax.plot(ke, label="KE (eV)")
        ax.plot(pe + ke, label="Total (eV)")
        ax.set_xlabel("Frame")
        ax.set_ylabel("Energy (eV)")
        ax.set_title(f"Drift: max |ΔE_tot| = "
                     f"{abs(drift_meV).max():.3f} meV/atom")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / "energy.png", dpi=150)
        plt.close(fig)
        print(f"  -> {out_dir / 'energy.png'}, {out_dir / 'energy.csv'}")

    # --- RDF (optional)
    if args.rdf_elements:
        print(f"Computing RDF for {args.rdf_elements} (rmax={args.rdf_rmax}) ...")
        try:
            from ase.geometry.analysis import Analysis
            ana = Analysis(frames)
            rdf, dists = ana.get_rdf(
                rmax=args.rdf_rmax, nbins=args.rdf_nbins,
                elements=tuple(args.rdf_elements), return_dists=True,
            )
            rdf_mean = np.mean(rdf, axis=0)
            r = dists[0] if isinstance(dists, list) else dists

            write_csv(out_dir / "rdf.csv",
                      ["r_angstrom", "g_r"],
                      [[float(rr), float(gg)] for rr, gg in zip(r, rdf_mean)])

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(r, rdf_mean)
            ax.set_xlabel("r (Å)")
            ax.set_ylabel("g(r)")
            ax.set_title(f"RDF {args.rdf_elements[0]}-{args.rdf_elements[1]}")
            ax.grid(alpha=0.3)
            fig.tight_layout()
            fig.savefig(out_dir / "rdf.png", dpi=150)
            plt.close(fig)
            print(f"  -> {out_dir / 'rdf.png'}, {out_dir / 'rdf.csv'}")
        except Exception as e:
            print(f"  RDF failed: {e}")
            print("  (RDF requires PBC; check your trajectory has a cell.)")

    print()
    print("Summary:")
    print(f"  Mean RMSD vs frame {args.reference_frame}: {rmsd.mean():.3f} Å")
    print(f"  Max  RMSD                                 : {rmsd.max():.3f} Å")
    print(f"  Most flexible atom: index {int(rmsf.argmax())} "
          f"({symbols[int(rmsf.argmax())]}), RMSF {rmsf.max():.3f} Å")
    return 0


def _safe_get(atoms, method_name: str) -> float:
    try:
        return float(getattr(atoms, method_name)())
    except Exception:
        return float("nan")


if __name__ == "__main__":
    raise SystemExit(main())
