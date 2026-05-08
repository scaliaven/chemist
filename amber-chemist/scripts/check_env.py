#!/usr/bin/env python3
"""Detect Amber-stack tools and print a tagged status report.

When to use:
    Run this once at the start of any non-trivial amber-chemist task. The
    output determines which workflows the skill should recommend (REMD
    needs MPI; MMPBSA needs MMPBSA.py; alanine-scan needs ParmEd).

When NOT to use:
    If you've already run it earlier in this session and nothing has
    been installed since, the cached output is fine — don't re-run.

Output format:
    Each line is prefixed with [OK], [MISSING], [INFO], or [SUMMARY] so
    it is both human-readable and grep-friendly:

        grep '^\\[MISSING\\]' check_env.txt

    The [SUMMARY] line names concrete capabilities the environment
    supports right now.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from typing import Optional


def _try_import(module_name: str) -> Optional[str]:
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return None
    return getattr(mod, "__version__", "(version unknown)")


def _detect_cuda() -> dict:
    try:
        import torch
    except ImportError:
        return {"torch_present": False, "available": False}
    if not torch.cuda.is_available():
        return {"torch_present": True, "available": False}
    try:
        free, total = torch.cuda.mem_get_info(0)
        return {
            "torch_present": True,
            "available": True,
            "n_devices": torch.cuda.device_count(),
            "primary_device": torch.cuda.get_device_name(0),
            "free_gb": free / (1024 ** 3),
            "total_gb": total / (1024 ** 3),
        }
    except Exception:
        return {
            "torch_present": True,
            "available": True,
            "n_devices": torch.cuda.device_count(),
            "primary_device": torch.cuda.get_device_name(0),
            "free_gb": float("nan"),
            "total_gb": float("nan"),
        }


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Report which Amber-stack tools are installed. Each line is "
            "tagged [OK]/[MISSING]/[INFO]/[SUMMARY] for both humans and grep."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--summary-only", action="store_true",
                   help="Print only the [SUMMARY] line.")
    args = p.parse_args()

    # AmberTools binaries
    antechamber = shutil.which("antechamber")
    parmchk2 = shutil.which("parmchk2")
    tleap = shutil.which("tleap")
    pdb4amber = shutil.which("pdb4amber")
    reduce = shutil.which("reduce")
    ambpdb = shutil.which("ambpdb")
    parmed_bin = shutil.which("parmed")
    cpptraj = shutil.which("cpptraj")
    mmpbsa = shutil.which("MMPBSA.py")
    mmpbsa_mpi = shutil.which("MMPBSA.py.MPI")

    # MD engines (plain + MPI)
    sander = shutil.which("sander")
    pmemd = shutil.which("pmemd")
    pmemd_cuda = shutil.which("pmemd.cuda")
    sander_mpi = shutil.which("sander.MPI")
    pmemd_mpi = shutil.which("pmemd.MPI")
    pmemd_cuda_mpi = shutil.which("pmemd.cuda.MPI")

    amber_home = os.environ.get("AMBERHOME")

    # Python deps
    parmed_py = _try_import("parmed")
    netcdf4_py = _try_import("netCDF4")
    matplotlib = _try_import("matplotlib")
    numpy_v = _try_import("numpy")
    ase_v = _try_import("ase")

    cuda = _detect_cuda()

    lines: list[str] = []
    lines.append(f"[INFO] Python {sys.version.split()[0]}")

    # AmberTools core
    if antechamber and parmchk2 and tleap:
        lines.append("[OK] AmberTools core — antechamber, parmchk2, tleap on PATH")
    else:
        missing = [n for n, v in (("antechamber", antechamber),
                                  ("parmchk2", parmchk2),
                                  ("tleap", tleap)) if v is None]
        lines.append(
            f"[MISSING] AmberTools core — {', '.join(missing)} not on PATH. "
            "Install AmberTools (free): https://ambermd.org/GetAmber.php"
        )

    for label, path in (("pdb4amber", pdb4amber), ("reduce", reduce),
                        ("ambpdb", ambpdb), ("parmed (binary)", parmed_bin)):
        if path:
            lines.append(f"[OK] {label} at {path}")
        else:
            lines.append(f"[MISSING] {label} — bundled with AmberTools")

    # cpptraj + MMPBSA
    if cpptraj:
        lines.append(f"[OK] cpptraj at {cpptraj}")
    else:
        lines.append("[MISSING] cpptraj — bundled with AmberTools; needed by amber_analyze.py and amber_sp.py --mode trajectory")

    if mmpbsa:
        lines.append(f"[OK] MMPBSA.py at {mmpbsa}")
    else:
        lines.append("[MISSING] MMPBSA.py — bundled with AmberTools; needed by amber_score.py")
    if mmpbsa_mpi:
        lines.append(f"[OK] MMPBSA.py.MPI at {mmpbsa_mpi} — enables --mpi in amber_score.py")
    else:
        lines.append("[INFO] MMPBSA.py.MPI not on PATH — amber_score.py --mpi N will fall back to serial")

    # Plain MD engines
    plain_engines = []
    if pmemd_cuda:
        plain_engines.append(f"pmemd.cuda ({pmemd_cuda})")
    if pmemd:
        plain_engines.append(f"pmemd ({pmemd})")
    if sander:
        plain_engines.append(f"sander ({sander})")
    if plain_engines:
        lines.append("[OK] Plain MD engine(s): " + "; ".join(plain_engines))
    else:
        lines.append(
            "[MISSING] No plain Amber MD engine on PATH (pmemd.cuda, pmemd, sander). "
            "AmberTools25 is fully open-source including pmemd.cuda."
        )

    # MPI engines (REMD)
    mpi_engines = []
    if pmemd_cuda_mpi:
        mpi_engines.append(f"pmemd.cuda.MPI ({pmemd_cuda_mpi})")
    if pmemd_mpi:
        mpi_engines.append(f"pmemd.MPI ({pmemd_mpi})")
    if sander_mpi:
        mpi_engines.append(f"sander.MPI ({sander_mpi})")
    if mpi_engines:
        lines.append("[OK] MPI MD engine(s) for REMD: " + "; ".join(mpi_engines))
    else:
        lines.append(
            "[MISSING] No MPI Amber MD engine on PATH (pmemd.cuda.MPI, pmemd.MPI, "
            "sander.MPI). Required for REMD."
        )

    if not amber_home and (antechamber or sander or pmemd):
        lines.append(
            "[INFO] AMBERHOME unset — Amber binaries are on PATH but the "
            "environment may not be fully sourced."
        )

    # CUDA / GPU
    if cuda["available"]:
        free_str = (f"{cuda['free_gb']:.1f}/{cuda['total_gb']:.1f} GB free"
                    if cuda["free_gb"] == cuda["free_gb"]
                    else "memory unknown")
        lines.append(
            f"[OK] CUDA available — {cuda['n_devices']} device(s); "
            f"GPU 0: {cuda['primary_device']} ({free_str})"
        )
    elif cuda["torch_present"]:
        lines.append("[INFO] torch present but CUDA unavailable — pmemd.cuda will not run")
    else:
        lines.append("[INFO] torch not installed — CUDA detection skipped (pmemd.cuda may still work via its own CUDA runtime)")

    # Python deps
    if parmed_py:
        lines.append(f"[OK] parmed (Python) {parmed_py} — enables alanine-scan and per-residue MMPBSA")
    else:
        lines.append("[MISSING] parmed (Python) — install with: pip install parmed (or via AmberTools)")

    if netcdf4_py:
        lines.append(f"[OK] netCDF4 {netcdf4_py} — required for cpptraj NetCDF I/O")
    else:
        lines.append("[MISSING] netCDF4 — install with: pip install netCDF4")

    if matplotlib:
        lines.append(f"[OK] matplotlib {matplotlib}")
    else:
        lines.append("[MISSING] matplotlib — required by amber_analyze.py for plots")

    if numpy_v:
        lines.append(f"[OK] numpy {numpy_v}")
    else:
        lines.append("[MISSING] numpy")

    if ase_v:
        lines.append(f"[INFO] ASE {ase_v} detected — not required by amber-chemist")

    # Capability summary
    capabilities: list[str] = []
    has_at = bool(antechamber and parmchk2 and tleap)
    has_plain = bool(plain_engines)
    has_mpi = bool(mpi_engines)
    if has_at and has_plain:
        engine_label = ("pmemd.cuda" if pmemd_cuda
                        else "pmemd" if pmemd else "sander")
        capabilities.append(
            f"GAFF2 small-molecule MD with AM1-BCC (antechamber + tleap + {engine_label})"
        )
        capabilities.append("implicit-solvent MD (GB)")
    if has_mpi:
        mpi_label = ("pmemd.cuda.MPI" if pmemd_cuda_mpi
                     else "pmemd.MPI" if pmemd_mpi else "sander.MPI")
        capabilities.append(f"T-REMD via {mpi_label} (-rem 1)")
    if cpptraj:
        capabilities.append("cpptraj-driven RMSD/RMSF/RDF/hbond/radgyr analysis")
        capabilities.append("per-frame trajectory energy decomposition via cpptraj esander")
    if mmpbsa:
        capabilities.append("MMPBSA / MMGBSA endpoint binding free energy")
    if mmpbsa and parmed_py:
        capabilities.append("per-residue MMPBSA decomposition + alanine scanning")

    if capabilities:
        summary = "You can currently run: " + "; ".join(capabilities) + "."
    else:
        summary = (
            "AmberTools or an MD engine is missing — install AmberTools "
            "from https://ambermd.org/GetAmber.php"
        )
    summary_line = f"[SUMMARY] {summary}"
    lines.append(summary_line)

    if args.summary_only:
        print(summary_line)
        return 0 if has_at else 1

    for line in lines:
        print(line)
    return 0 if has_at else 1


if __name__ == "__main__":
    raise SystemExit(main())
