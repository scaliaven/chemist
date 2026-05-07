#!/usr/bin/env python3
"""Detect installed simulation backends and print a tagged status report.

When to use:
    Run this once at the start of any non-trivial ase-chemist task. The
    output determines which calculator the skill should recommend.

When NOT to use:
    If you've already run it earlier in this session and the user hasn't
    installed or uninstalled anything since, the cached output is fine —
    don't re-run it before every script call.

Output format:
    Each line is prefixed with [OK], [MISSING], [INFO], or [SUMMARY] so it
    is both human-readable and grep-friendly:

        grep '^\\[MISSING\\]' check_env.txt

    The [SUMMARY] line names concrete capabilities the environment supports
    right now.
"""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from typing import Optional


def _try_import(module_name: str) -> Optional[str]:
    """Return module's __version__, or None if not importable."""
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return None
    return getattr(mod, "__version__", "(version unknown)")


def _probe_tblite_ase() -> Optional[str]:
    """Confirm tblite's C extension actually loads (not just the Python shim).

    Returns None if usable, or the error message if the C extension fails.
    """
    try:
        from tblite.ase import TBLite  # noqa: F401
    except Exception as e:
        return str(e)
    return None


def _detect_cuda() -> dict:
    """Detect CUDA availability via torch. Used for ML-potential sizing.

    Returns dict with keys:
      torch_present : bool
      available     : bool
      n_devices     : int (when available)
      primary_device: str (when available)
      free_gb       : float (when available)
      total_gb      : float (when available)
    """
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
        # mem_get_info can fail on older torch / unusual drivers
        return {
            "torch_present": True,
            "available": True,
            "n_devices": torch.cuda.device_count(),
            "primary_device": torch.cuda.get_device_name(0),
            "free_gb": float("nan"),
            "total_gb": float("nan"),
        }


def _v2_preview_lines() -> list[str]:
    """Detection block for v2 backends (Amber, Gaussian, ML potentials).

    None of these affect the v1 capability summary. Each line is prefixed
    with [v2 preview] so it is grep-friendly and visually separate from
    v1 status lines. "Available" here means "detected on the system" — it
    does NOT mean "supported by the skill yet"; the trailing arrow on each
    backend points at the stub reference that explains the limit.
    """
    out: list[str] = []
    out.append(
        "[v2 preview] (detection only — these backends are NOT yet "
        "supported by the skill)"
    )

    # --- Other ML potentials (MACE has been promoted to a supported
    #     backend; CHGNet, M3GNet, SevenNet, Orb remain v2-preview).
    ml_packages = [
        ("CHGNet",   "chgnet"),
        ("M3GNet",   "matgl"),
        ("SevenNet", "sevenn"),
        ("Orb",      "orb_models"),
    ]
    any_ml_available = False
    for label, modname in ml_packages:
        version = _try_import(modname)
        if version:
            any_ml_available = True
            out.append(
                f"[v2 preview] {label + ':':<10}available ({modname} {version})"
            )
        else:
            out.append(f"[v2 preview] {label + ':':<10}not installed")
    if any_ml_available:
        out.append(
            "[v2 preview]            → not yet supported by skill, "
            "see references/ml_potentials.md"
        )
    else:
        out.append(
            "[v2 preview]            → other ML potentials planned for "
            "v2.2+, see references/ml_potentials.md"
        )

    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report which simulation backends are installed. Each line is "
            "tagged [OK]/[MISSING]/[INFO]/[SUMMARY] for both humans and grep."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Print only the [SUMMARY] line.",
    )
    args = parser.parse_args()

    ase_version = _try_import("ase")
    tblite_version = _try_import("tblite")
    xtb_python_version = _try_import("xtb")
    mda_version = _try_import("MDAnalysis")
    matplotlib_version = _try_import("matplotlib")
    numpy_version = _try_import("numpy")
    mace_version = _try_import("mace")
    torch_version = _try_import("torch")
    # Note: no cclib detection. Gaussian thermochem parsing is in-house
    # (scripts/_gaussian_log.py) so the skill stays "everything through
    # ASE-or-our-own-code".

    xtb_binary = shutil.which("xtb")
    cuda = _detect_cuda()

    # AmberTools / Amber binaries — promoted to supported in v1.3.
    antechamber_bin = shutil.which("antechamber")
    parmchk2_bin = shutil.which("parmchk2")
    tleap_bin = shutil.which("tleap")
    sander_bin = shutil.which("sander")
    pmemd_bin = shutil.which("pmemd")
    pmemd_cuda_bin = shutil.which("pmemd.cuda")
    amber_home = os.environ.get("AMBERHOME")

    # Gaussian — promoted to supported in v1.4.
    g16_bin = shutil.which("g16")
    g09_bin = shutil.which("g09")
    gauss_exedir = os.environ.get("GAUSS_EXEDIR")
    gauss_scrdir = os.environ.get("GAUSS_SCRDIR")

    lines: list[str] = []

    # Python interpreter
    lines.append(f"[INFO] Python {sys.version.split()[0]}")

    # Required: ASE
    if ase_version:
        lines.append(f"[OK] ASE {ase_version}")
    else:
        lines.append("[MISSING] ASE — install with: pip install ase")

    # Required: numpy (ASE pulls it in but check separately)
    if numpy_version:
        lines.append(f"[OK] numpy {numpy_version}")
    else:
        lines.append("[MISSING] numpy")

    # xTB — three separate paths, reported separately
    if tblite_version:
        # tblite/__init__.py loads even when the C extension is broken;
        # probe the calculator import so we don't lie about usability.
        tblite_error = _probe_tblite_ase()
        if tblite_error is None:
            lines.append(
                f"[OK] tblite (Python) {tblite_version} — primary xTB path "
                f"(GFN1-xTB, GFN2-xTB)"
            )
        else:
            lines.append(
                f"[BROKEN] tblite {tblite_version} installed but C extension "
                f"unloadable: {tblite_error}. "
                f"Try: conda install -c conda-forge tblite-python"
            )
    else:
        lines.append(
            "[MISSING] tblite (Python) — primary xTB path. "
            "Install with: pip install tblite "
            "(or, on HPC/conda systems: conda install -c conda-forge tblite-python)"
        )

    if xtb_python_version:
        lines.append(
            f"[INFO] xtb-python {xtb_python_version} present "
            "(deprecated upstream — prefer tblite)"
        )
    else:
        lines.append(
            "[INFO] xtb-python not installed (deprecated; tblite is the "
            "supported replacement)"
        )

    if xtb_binary:
        lines.append(
            f"[OK] xtb binary on PATH at {xtb_binary} — enables GFN0 and GFN-FF"
        )
    else:
        lines.append(
            "[MISSING] xtb binary not on PATH — needed for GFN0 / GFN-FF only. "
            "Install with: conda install -c conda-forge xtb"
        )

    # MACE foundation models
    if mace_version:
        lines.append(
            f"[OK] mace {mace_version} — MACE-MP-0 (materials) and "
            "MACE-OFF (organics) foundation models"
        )
    else:
        lines.append(
            "[MISSING] mace — MACE foundation models for systems past the "
            "xTB size cliff (~1k atoms). Install with: pip install mace-torch"
        )

    # CUDA / GPU
    if cuda["available"]:
        free_str = (f"{cuda['free_gb']:.1f}/{cuda['total_gb']:.1f} GB free"
                    if cuda["free_gb"] == cuda["free_gb"]  # NaN check
                    else "memory unknown")
        lines.append(
            f"[OK] CUDA available — {cuda['n_devices']} device(s); "
            f"GPU 0: {cuda['primary_device']} ({free_str})"
        )
    elif cuda["torch_present"]:
        lines.append(
            "[INFO] torch present but CUDA unavailable — MACE will run on CPU "
            "(~10x slower; size cliff effectively halves)"
        )
    else:
        lines.append(
            "[MISSING] torch — required by mace-torch. "
            "Install with: pip install torch"
        )

    # AmberTools / Amber (v1.3 supports GAFF2 small-molecule MD; protein/NA
    # MD via ff19SB+OPC / OL21 is deferred to v2.3).
    if antechamber_bin and parmchk2_bin and tleap_bin:
        lines.append(
            f"[OK] AmberTools — antechamber, parmchk2, tleap all on PATH"
        )
    else:
        missing_at = [
            n for n, p in (
                ("antechamber", antechamber_bin),
                ("parmchk2", parmchk2_bin),
                ("tleap", tleap_bin),
            ) if p is None
        ]
        if missing_at:
            lines.append(
                f"[MISSING] AmberTools — {', '.join(missing_at)} not on PATH. "
                "Install AmberTools (free): https://ambermd.org/GetAmber.php"
            )

    md_engines = []
    if pmemd_cuda_bin:
        md_engines.append(f"pmemd.cuda ({pmemd_cuda_bin})")
    if pmemd_bin:
        md_engines.append(f"pmemd ({pmemd_bin})")
    if sander_bin:
        md_engines.append(f"sander ({sander_bin})")
    if md_engines:
        lines.append("[OK] Amber MD engine(s): " + "; ".join(md_engines))
    else:
        lines.append(
            "[MISSING] No Amber MD engine on PATH (need pmemd.cuda, pmemd, "
            "or sander). AmberTools25 is fully open-source including pmemd.cuda."
        )

    if not amber_home and (antechamber_bin or sander_bin or pmemd_bin):
        lines.append(
            "[INFO] AMBERHOME unset — Amber binaries are on PATH but the "
            "environment may not be fully sourced (some scripts depend on it)."
        )

    # Gaussian (v1.4 supports SP / Opt / Freq via ase.calculators.gaussian.Gaussian)
    if g16_bin:
        lines.append(f"[OK] Gaussian — g16 at {g16_bin}")
    elif g09_bin:
        lines.append(
            f"[OK] Gaussian — g09 at {g09_bin} (g16 not on PATH; gaussian_*.py "
            "auto-falls back)"
        )
    else:
        lines.append(
            "[MISSING] Gaussian — neither g16 nor g09 on PATH. Required for "
            "DFT-quality SP/Opt/Freq via gaussian_*.py. License-gated; see "
            "https://gaussian.com/"
        )

    if (g16_bin or g09_bin) and not gauss_exedir:
        lines.append(
            "[INFO] GAUSS_EXEDIR unset — Gaussian binary is on PATH but the "
            "environment may not be fully sourced. Source the Gaussian env "
            "(e.g. `source $g16root/g16/bsd/g16.profile`) to set it."
        )
    if (g16_bin or g09_bin) and not gauss_scrdir:
        lines.append(
            "[INFO] GAUSS_SCRDIR unset — Gaussian writes scratch to its "
            "default location, which may be a small filesystem. Set "
            "GAUSS_SCRDIR to a fast, large-quota path for non-trivial jobs."
        )

    # Analysis stack
    if mda_version:
        lines.append(f"[OK] MDAnalysis {mda_version}")
    else:
        lines.append(
            "[MISSING] MDAnalysis — install with: pip install mdanalysis "
            "(only needed for protein/DCD/XTC trajectory analysis)"
        )

    if matplotlib_version:
        lines.append(f"[OK] matplotlib {matplotlib_version}")
    else:
        lines.append(
            "[MISSING] matplotlib — install with: pip install matplotlib "
            "(required by analyze_traj.py)"
        )

    # Capability summary — only count tblite if its C extension actually loads.
    tblite_works = bool(tblite_version) and _probe_tblite_ase() is None
    capabilities: list[str] = []
    if ase_version:
        # Always available with ASE
        opt_calcs = ["EMT", "LJ"]
        md_calcs = ["EMT", "LJ", "TIP3P"]
        if tblite_works:
            opt_calcs.append("xTB")
            md_calcs.append("xTB")
        if mace_version:
            opt_calcs.append("MACE")
            md_calcs.append("MACE")
        capabilities.append(
            f"geometry optimization with {'/'.join(opt_calcs)}"
        )
        capabilities.append(f"MD with {'/'.join(md_calcs)}")
        capabilities.append("vibrational analysis (Vibrations + thermochem)")
        capabilities.append("structure building (ase.build)")
        capabilities.append("NEB (climb-image, no turnkey script)")
        if matplotlib_version:
            capabilities.append("trajectory analysis (RMSD/RMSF/RDF/drift)")
        else:
            capabilities.append("trajectory analysis (text only — no plots)")
        if tblite_works:
            capabilities.append(
                "electronic observables via xTB (HOMO-LUMO/dipole/charges)"
            )
        if xtb_binary:
            capabilities.append("GFN-FF / GFN0 via xtb binary")
        if mda_version:
            capabilities.append("protein-trajectory analysis (MDAnalysis)")
        if mace_version and tblite_works:
            device = "GPU" if cuda["available"] else "CPU"
            capabilities.append(
                f"MACE foundation-model MD with mandatory xTB cross-"
                f"validation (on {device})"
            )
        if (antechamber_bin and parmchk2_bin and tleap_bin
                and (sander_bin or pmemd_bin or pmemd_cuda_bin)):
            engine_label = (
                "pmemd.cuda" if pmemd_cuda_bin
                else "pmemd" if pmemd_bin
                else "sander"
            )
            capabilities.append(
                f"GAFF2 small-molecule MD with AM1-BCC charges "
                f"(antechamber + tleap + {engine_label}; protein/NA "
                f"deferred to v2.3)"
            )
        if g16_bin or g09_bin:
            gauss_label = "g16" if g16_bin else "g09"
            capabilities.append(
                f"Gaussian DFT SP/Opt/Freq+thermochem via {gauss_label}"
            )

    if capabilities:
        summary = "You can currently run: " + "; ".join(capabilities) + "."
    else:
        summary = (
            "ASE itself is missing — install with: "
            "pip install ase tblite mdanalysis matplotlib"
        )

    summary_line = f"[SUMMARY] {summary}"
    lines.append(summary_line)

    if args.summary_only:
        print(summary_line)
        return 0 if ase_version else 1

    for line in lines:
        print(line)

    # v2 backends — printed AFTER the v1 summary, separated by a blank line
    # so they cannot be mistaken for currently-supported capabilities.
    print()
    for line in _v2_preview_lines():
        print(line)

    return 0 if ase_version else 1


if __name__ == "__main__":
    raise SystemExit(main())
