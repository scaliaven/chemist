#!/usr/bin/env python3
"""Run Amber MD on a parameterized small-molecule system.

When to use:
    You have a `.prmtop` + `.rst7` pair (from `parameterize_gaff2.py`,
    or a user-supplied topology) and you want to run minimization,
    heating, density equilibration, and production NPT MD. This
    script writes Amber `mdin` decks per stage, picks the best
    available engine (pmemd.cuda > pmemd > sander), shells out, and
    writes a NetCDF `.nc` trajectory you can hand to
    `analyze_traj.py`.

When NOT to use:
    Free energy, REMD, umbrella sampling, constant-pH, QM/MM —
    those are research workflows out of scope for v1.3.
    Protein / nucleic-acid systems with ff19SB / OL21 — those use a
    different parameterization and are deferred to v2.3; this
    script's `mdin` defaults are tuned for GAFF2 small molecules.
    Pre-existing trajectories you only want to analyze — go straight
    to `analyze_traj.py`.

Stages (`--protocol standard` runs all four; or use `--stage`):
    min      Minimization, 10000 cycles (5000 steepest, 5000 CG).
    heat     50 ps NVT, 0 → 300 K linear ramp, SHAKE on H bonds, 2 fs.
    density  100 ps NPT at 300 K / 1 atm, isotropic Berendsen barostat.
    prod     User-controlled NPT production (default 500 ps at 300 K).

Engine selection:
    Default: pmemd.cuda > pmemd > sander, picking the first available.
    Override with `--engine sander` (testing) or `--engine pmemd.cuda`.

Examples:
    # Full standard protocol
    python run_amber.py --prmtop system.prmtop --rst system.rst7 \\
        --protocol standard --output-dir run/

    # Just minimize then heat (skip density/production)
    python run_amber.py --prmtop system.prmtop --rst system.rst7 \\
        --stage min --output-dir run/
    python run_amber.py --prmtop system.prmtop \\
        --rst run/min.rst7 --stage heat --output-dir run/
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Optional


ENGINE_PREFERENCE = ("pmemd.cuda", "pmemd", "sander")


def pick_engine(preferred: Optional[str]) -> str:
    if preferred is not None:
        path = shutil.which(preferred)
        if path is None:
            raise SystemExit(
                f"Requested engine '{preferred}' is not on PATH. "
                f"Drop --engine to auto-select, or fix PATH."
            )
        return preferred
    for engine in ENGINE_PREFERENCE:
        if shutil.which(engine):
            return engine
    raise SystemExit(
        "No Amber MD engine on PATH. Need one of: "
        + ", ".join(ENGINE_PREFERENCE) + ". "
        "Run scripts/check_env.py for detection details."
    )


def render_min(temp: float) -> str:
    return f"""\
Minimization (10000 cycles total: 5000 steepest, 5000 conjugate gradient)
&cntrl
  imin=1, maxcyc=10000, ncyc=5000,
  ntb=1, cut=10.0,
  ntpr=100, ntwx=0,
&end
"""


def render_heat(temp: float, n_steps: int) -> str:
    return f"""\
Heating 0 -> {temp:.1f} K, {n_steps * 0.002:.1f} ps NVT, SHAKE on H, 2 fs
&cntrl
  imin=0, irest=0, ntx=1,
  nstlim={n_steps}, dt=0.002,
  ntb=1, ntp=0,
  ntc=2, ntf=2,
  cut=10.0,
  ntt=3, gamma_ln=2.0, ig=-1,
  tempi=0.0, temp0={temp:.1f},
  nmropt=1,
  ntpr=100, ntwx=500, ntwr=1000, ioutfm=1,
&end
&wt type='TEMP0', istep1=0, istep2={n_steps}, value1=0.0, value2={temp:.1f} &end
&wt type='END' &end
"""


def render_density(temp: float, n_steps: int) -> str:
    return f"""\
Density equilibration, {n_steps * 0.002:.1f} ps NPT at {temp:.1f} K
&cntrl
  imin=0, irest=1, ntx=5,
  nstlim={n_steps}, dt=0.002,
  ntb=2, ntp=1, taup=2.0,
  ntc=2, ntf=2,
  cut=10.0,
  ntt=3, gamma_ln=2.0, ig=-1,
  temp0={temp:.1f},
  ntpr=100, ntwx=500, ntwr=1000, ioutfm=1,
&end
"""


def render_prod(temp: float, n_steps: int) -> str:
    return f"""\
Production NPT, {n_steps * 0.002:.1f} ps at {temp:.1f} K
&cntrl
  imin=0, irest=1, ntx=5,
  nstlim={n_steps}, dt=0.002,
  ntb=2, ntp=1, taup=2.0,
  ntc=2, ntf=2,
  cut=10.0,
  ntt=3, gamma_ln=2.0, ig=-1,
  temp0={temp:.1f},
  ntpr=500, ntwx=500, ntwr=10000, ioutfm=1,
&end
"""


STAGE_RENDERERS = {
    "min":      render_min,
    "heat":     render_heat,
    "density":  render_density,
    "prod":     render_prod,
}


def run_stage(*, engine: str, stage: str, mdin: Path,
              prmtop: Path, in_rst: Path, out_dir: Path,
              ref_for_pos_restraints: Optional[Path] = None) -> Path:
    """Execute one Amber MD stage, return path to the output rst7."""
    out_mdout = out_dir / f"{stage}.mdout"
    out_rst = out_dir / f"{stage}.rst7"
    out_nc = out_dir / f"{stage}.nc"

    cmd = [
        engine, "-O",
        "-i", str(mdin),
        "-o", str(out_mdout),
        "-p", str(prmtop),
        "-c", str(in_rst),
        "-r", str(out_rst),
        "-x", str(out_nc),
    ]
    if ref_for_pos_restraints is not None:
        cmd += ["-ref", str(ref_for_pos_restraints)]

    print(f"$ {' '.join(cmd)}")
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        raise SystemExit(
            f"{engine} failed at stage '{stage}' (rc={rc}). "
            f"Inspect {out_mdout} for the error."
        )
    if not out_rst.exists():
        raise SystemExit(
            f"{engine} reported success but {out_rst} is missing."
        )
    return out_rst


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Run Amber MD on a parameterized small-molecule system. "
            "Standard protocol = min -> heat -> density -> prod. "
            "Engine selection: pmemd.cuda > pmemd > sander."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--prmtop", required=True, help="Amber topology .prmtop")
    p.add_argument("--rst", required=True,
                   help="Initial coordinates (.rst7 or .inpcrd).")
    p.add_argument("--output-dir", default=".",
                   help="Directory for mdin / mdout / nc / rst7 outputs.")
    p.add_argument("--protocol", default=None,
                   choices=["standard"],
                   help="Run a bundled multi-stage protocol. "
                        "'standard' = min -> heat -> density -> prod.")
    p.add_argument("--stage", default=None,
                   choices=list(STAGE_RENDERERS.keys()),
                   help="Run a single stage. Mutually exclusive with "
                        "--protocol.")
    p.add_argument("--engine", default=None,
                   choices=list(ENGINE_PREFERENCE),
                   help="Override engine auto-selection.")
    p.add_argument("--temperature", type=float, default=300.0,
                   help="Target temperature in K (heat ramp endpoint, "
                        "density and prod thermostat target).")
    p.add_argument("--heat-steps", type=int, default=25000,
                   help="Heat-stage step count (50 ps at 2 fs default).")
    p.add_argument("--density-steps", type=int, default=50000,
                   help="Density-stage step count (100 ps at 2 fs default).")
    p.add_argument("--prod-steps", type=int, default=250000,
                   help="Production step count (500 ps at 2 fs default).")
    args = p.parse_args()

    print("[amber] CARVE-OUT NOTE: the MD integration loop runs natively in")
    print("[amber]   pmemd / pmemd.cuda / sander, NOT through ASE. Amber is")
    print("[amber]   the only engine in ase-simulation that bypasses ASE;")
    print("[amber]   ase.calculators.amber.Amber is single-point only and")
    print("[amber]   rejects non-orthogonal cells, both fatal for MD. ASE")
    print("[amber]   handles structure I/O at the boundaries; the simulation")
    print("[amber]   itself is opaque to ASE. This carve-out is under review")
    print("[amber]   for removal — see references/amber.md §1 and PLAN.md")
    print("[amber]   §Phase 3.")
    print()

    if args.protocol and args.stage:
        raise SystemExit("--protocol and --stage are mutually exclusive.")
    if not args.protocol and not args.stage:
        raise SystemExit(
            "Pass either --protocol standard or --stage {min,heat,density,prod}."
        )

    prmtop = Path(args.prmtop).resolve()
    rst = Path(args.rst).resolve()
    if not prmtop.exists():
        raise SystemExit(f"prmtop not found: {prmtop}")
    if not rst.exists():
        raise SystemExit(f"initial coordinates not found: {rst}")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = pick_engine(args.engine)
    print(f"[amber] engine     : {engine}")
    print(f"[amber] prmtop     : {prmtop}")
    print(f"[amber] start rst  : {rst}")
    print(f"[amber] output dir : {out_dir}")
    print(f"[amber] target T   : {args.temperature} K")
    print()

    stage_steps = {
        "min": 0,  # min uses maxcyc, not nstlim
        "heat": args.heat_steps,
        "density": args.density_steps,
        "prod": args.prod_steps,
    }

    if args.protocol == "standard":
        stages = ["min", "heat", "density", "prod"]
    else:
        stages = [args.stage]

    current_rst = rst
    for stage in stages:
        renderer = STAGE_RENDERERS[stage]
        if stage == "min":
            mdin_text = renderer(args.temperature)
        else:
            mdin_text = renderer(args.temperature, stage_steps[stage])
        mdin = out_dir / f"{stage}.in"
        mdin.write_text(mdin_text)
        current_rst = run_stage(
            engine=engine, stage=stage, mdin=mdin,
            prmtop=prmtop, in_rst=current_rst, out_dir=out_dir,
        )
        print(f"[amber] stage '{stage}' done -> {current_rst}")

    print()
    print("All requested stages completed.")
    final_nc = out_dir / f"{stages[-1]}.nc"
    if final_nc.exists():
        print(f"Trajectory: {final_nc}")
        print("Analyze with:")
        print(f"  python scripts/analyze_traj.py --trajectory {final_nc} ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
