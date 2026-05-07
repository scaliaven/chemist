#!/usr/bin/env python3
"""Detect installed simulation backends and print a tagged status report.

When to use:
    Run this once at the start of any non-trivial ase-simulation task. The
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

    # --- Amber ---
    sander = shutil.which("sander")
    pmemd = shutil.which("pmemd")
    tleap = shutil.which("tleap")
    amber_home = os.environ.get("AMBERHOME")
    if sander or pmemd:
        engine, path = ("sander", sander) if sander else ("pmemd", pmemd)
        out.append(f"[v2 preview] Amber:    available ({engine} at {path})")
        if not tleap:
            out.append(
                "[v2 preview]            note: tleap not on PATH — "
                "v2 system prep will need it"
            )
        if not amber_home:
            out.append(
                "[v2 preview]            note: AMBERHOME unset — "
                "environment may not be sourced"
            )
        out.append(
            "[v2 preview]            → not yet supported by skill, "
            "see references/amber.md"
        )
    else:
        out.append("[v2 preview] Amber:    not detected")
        out.append(
            "[v2 preview]            → planned for v2, "
            "see references/amber.md"
        )

    # --- Gaussian ---
    g16 = shutil.which("g16")
    g09 = shutil.which("g09")
    gauss_exedir = os.environ.get("GAUSS_EXEDIR")
    gauss_scrdir = os.environ.get("GAUSS_SCRDIR")
    if g16 or g09:
        version, path = ("g16", g16) if g16 else ("g09", g09)
        out.append(f"[v2 preview] Gaussian: available ({version} at {path})")
        if not gauss_exedir:
            out.append(
                "[v2 preview]            note: GAUSS_EXEDIR unset — "
                "Gaussian env may not be sourced"
            )
        if not gauss_scrdir:
            out.append(
                "[v2 preview]            note: GAUSS_SCRDIR unset — "
                "scratch path required for non-trivial jobs"
            )
        out.append(
            "[v2 preview]            → not yet supported by skill, "
            "see references/gaussian.md"
        )
    else:
        out.append("[v2 preview] Gaussian: not detected")
        out.append(
            "[v2 preview]            → planned for v2, "
            "see references/gaussian.md"
        )

    # --- ML potentials ---
    ml_packages = [
        ("MACE",     "mace_torch"),
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
            "[v2 preview]            → ML potentials planned for v2, "
            "see references/ml_potentials.md"
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

    xtb_binary = shutil.which("xtb")

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
