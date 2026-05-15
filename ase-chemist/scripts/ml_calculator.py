#!/usr/bin/env python3
"""Construct MACE foundation-model ASE calculators (MACE-MP-0 / MACE-OFF).

When to use:
    The user wants to run MD or optimization on a system that is too
    large for GFN2-xTB (~1k+ atoms) but does not need full DFT. MACE
    foundation models give roughly DFT-quality energies and forces for
    systems they are trained on (organics for MACE-OFF; crystals and
    inorganic materials for MACE-MP-0).

When NOT to use:
    Systems below ~500 atoms — GFN2-xTB is faster and more honest.
    Liquid mixtures (e.g. ethanol-water) — known qualitative failure.
    Anywhere the cross-validation overhead in run_md.py is unacceptable.

Routing:
    All atoms in {H, C, N, O, P, S, F, Cl, Br, I} → MACE-OFF (organics).
    Otherwise → MACE-MP-0 (materials, 89-element coverage).
    `system_class="organic"` or `"materials"` overrides routing.
"""

from __future__ import annotations

from typing import Optional

# MACE-OFF was trained on these elements. Pure-organic shorthand.
MACE_OFF_ELEMENTS = frozenset(
    {"H", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"}
)


def _select_target_for_atoms(atoms) -> str:
    elements = set(atoms.get_chemical_symbols())
    if elements.issubset(MACE_OFF_ELEMENTS):
        return "mace_off"
    return "mace_mp"


def _detect_device(prefer: Optional[str]) -> tuple[str, bool]:
    """Return (device, fell_back_to_cpu_silently)."""
    if prefer is not None:
        return prefer, False
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", False
    except ImportError:
        pass
    return "cpu", True


def make_ml_calc(atoms, *, system_class: Optional[str] = None,
                 device: Optional[str] = None,
                 model_size: str = "medium"):
    """Return a MACE ASE Calculator routed by element set.

    Parameters
    ----------
    atoms : ase.Atoms
        Live structure — used for element-based auto-routing.
    system_class : {"organic", "materials"} or None
        If set, overrides element-based routing.
    device : {"cuda", "cpu"} or None
        Inference device. None auto-detects (CUDA if available).
    model_size : {"small", "medium", "large"}
        MACE foundation-model checkpoint size.
    """
    if system_class not in (None, "organic", "materials"):
        raise SystemExit(
            f"system_class must be 'organic' or 'materials' "
            f"(got {system_class!r})."
        )

    if system_class == "organic":
        target = "mace_off"
    elif system_class == "materials":
        target = "mace_mp"
    else:
        target = _select_target_for_atoms(atoms)

    chosen_device, cpu_fallback = _detect_device(device)
    if cpu_fallback:
        print(
            "[mace] CUDA not available — falling back to CPU "
            "(expect ~10x slowdown vs GPU)"
        )

    try:
        if target == "mace_off":
            from mace.calculators import mace_off
            calc = mace_off(model=model_size, device=chosen_device)
            print(
                f"[mace] MACE-OFF ({model_size}) on {chosen_device} "
                f"— pure-organic routing, {len(atoms)} atoms"
            )
        else:
            from mace.calculators import mace_mp
            calc = mace_mp(model=model_size, device=chosen_device)
            elements = sorted(set(atoms.get_chemical_symbols()))
            print(
                f"[mace] MACE-MP-0 ({model_size}) on {chosen_device} "
                f"— elements {','.join(elements)}, {len(atoms)} atoms"
            )
    except ImportError as e:
        raise SystemExit(
            f"mace-torch is not installed: {e}\n"
            "Install with: pip install mace-torch\n"
            "Run scripts/check_env.py to verify."
        ) from e

    if len(atoms) > 1500:
        print(
            f"[mace] WARNING: {len(atoms)} atoms is near the practical "
            "ceiling on a 40 GB GPU (~1-2k atoms with MACE medium). "
            "If you hit OOM, drop to model_size='small' or shrink the "
            "system. CPU mode roughly halves this ceiling."
        )

    return calc


__all__ = ["make_ml_calc", "MACE_OFF_ELEMENTS"]


if __name__ == "__main__":
    # Smoke test: print routing decision for a structure passed on argv.
    import argparse
    from ase.io import read

    p = argparse.ArgumentParser(
        description=(
            "Print which MACE model would be used for a given structure. "
            "Does not load the model."
        )
    )
    p.add_argument("--structure", required=True)
    p.add_argument("--system-class", default=None,
                   choices=["organic", "materials"])
    args = p.parse_args()

    atoms = read(args.structure)
    elements = sorted(set(atoms.get_chemical_symbols()))
    if args.system_class == "organic":
        target = "mace_off"
    elif args.system_class == "materials":
        target = "mace_mp"
    else:
        target = _select_target_for_atoms(atoms)
    print(f"Atoms       : {len(atoms)}")
    print(f"Elements    : {','.join(elements)}")
    print(f"Routing     : {target}")
