"""Shared calculator factory for optimize.py / run_md.py / single_point.py.

Centralizes the EMT / LJ / TIP3P / xTB / MACE dispatch so each script
gets the same LJ kwarg handling, the same tblite [BROKEN] error message,
and the same MACE element-set routing.
"""

from __future__ import annotations


def build_calculator(name: str, *, atoms=None, xtb_method: str = "GFN2-xTB",
                     charge: int = 0, multiplicity: int = 1,
                     lj_epsilon: float | None = None,
                     lj_sigma: float | None = None,
                     lj_rc: float | None = None,
                     mace_system_class: str | None = None,
                     mace_device: str | None = None,
                     mace_size: str = "medium"):
    if name == "mace":
        if atoms is None:
            raise SystemExit(
                "build_calculator(name='mace') requires atoms= for "
                "element-based routing."
            )
        from ml_calculator import make_ml_calc
        return make_ml_calc(
            atoms, system_class=mace_system_class,
            device=mace_device, model_size=mace_size,
        )
    if name == "emt":
        from ase.calculators.emt import EMT
        return EMT()
    if name == "lj":
        from ase.calculators.lj import LennardJones
        kwargs = {}
        if lj_epsilon is not None:
            kwargs["epsilon"] = lj_epsilon
        if lj_sigma is not None:
            kwargs["sigma"] = lj_sigma
        if lj_rc is not None:
            kwargs["rc"] = lj_rc
        elif lj_sigma is not None:
            kwargs["rc"] = 3.0 * lj_sigma
        if kwargs:
            eps_s = f"{kwargs.get('epsilon', 1.0):.4g} eV"
            sig_s = f"{kwargs.get('sigma', 1.0):.4g} Å"
            rc_s = (f"{kwargs['rc']:.4g} Å" if "rc" in kwargs
                    else "ASE default")
            print(f"[lj] ε={eps_s}  σ={sig_s}  rc={rc_s}")
        else:
            print("[lj] reduced units (ε=1, σ=1) — toy parameters; "
                  "for real noble gases pass --epsilon/--sigma "
                  "(see references/ase_core.md §LJ parameters)")
        return LennardJones(**kwargs)
    if name == "tip3p":
        from ase.calculators.tip3p import TIP3P
        return TIP3P()
    if name == "xtb":
        try:
            from tblite.ase import TBLite
        except ImportError as e:
            raise SystemExit(
                f"tblite calculator unavailable: {e}\n"
                "Run `scripts/check_env.py` to see whether tblite is missing "
                "or installed-but-broken. On HPC/conda systems prefer "
                "`conda install -c conda-forge tblite-python`; on a clean "
                "pip environment, `pip install tblite`. Or pick a different "
                "--calculator."
            ) from e
        return TBLite(method=xtb_method, charge=charge,
                      multiplicity=multiplicity, verbosity=0)
    raise SystemExit(f"Unknown calculator: {name}")


__all__ = ["build_calculator"]
