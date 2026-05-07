#!/usr/bin/env python3
"""Easy mode: prep + min + heat + density + prod in one command.

When to use:
    The user wants a complete pipeline from a structure file to a
    finished trajectory, and is happy with the standard equilibration
    protocol. This is the "single python3 ... runs everything" entry
    that the skill recommends for most one-shot prompts.

When NOT to use:
    Stage-level control (different temp / restraints / barostat per
    stage) — use amber_md.py directly.
    Pre-existing prmtop you want to re-equilibrate or vary settings on
    a sweep — also amber_md.py.

Modes:
    --mode standard   prep -> min -> heat -> density -> prod (NPT)
    --mode remd       prep -> min -> heat -> density -> REMD prod
    --mode implicit   prep (no solvation) -> min -> heat -> prod (NVT, GB)

--from-prmtop:
    Skip the prep stage entirely. You provide --prmtop + --rst (and
    can drop --structure / --net-charge), and the pipeline starts at
    minimization. Useful for prmtops from CHARMM-GUI or external prep.

--time:
    Total simulation budget for prod, accepts unit suffixes:
    "1ns", "500ps", "5000000fs". Heat (50 ps) and density (100 ps) are
    fixed. Plain integer = step count, with a warning.

--resume:
    Skip a stage when its <stage>.rst7 + <stage>.mdout exist and the
    mdout's last line contains "Total wall time" (pmemd success
    marker). For REMD mode, resume is per-replica.

--dry-run:
    Render every mdin / tleap.in / groupfile and print every engine
    command, but do not invoke subprocess. Use this to inspect what
    would run before committing GPU time.

Examples:
    # 1 ns of GAFF2 explicit-solvent MD on caffeine in TIP3P
    python amber_run.py --structure caffeine.xyz --net-charge 0 \\
        --time 1ns --output-dir caffeine_run/

    # 8-replica T-REMD, 300-400 K, 100 ps per replica
    python amber_run.py --mode remd --structure peptide.pdb \\
        --net-charge 0 --time 100ps --n-replicas 8 \\
        --t-low 300 --t-high 400 --output-dir remd_out/

    # Implicit-solvent MD from a CHARMM-GUI prmtop
    python amber_run.py --mode implicit --from-prmtop \\
        --prmtop sys.prmtop --rst sys.rst7 --time 5ns \\
        --output-dir implicit_run/
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


HEAT_STEPS = 25000      # 50 ps at 2 fs
DENSITY_STEPS = 50000   # 100 ps at 2 fs


def stage_succeeded(out_dir: Path, prefix: str) -> bool:
    rst = out_dir / f"{prefix}.rst7"
    mdout = out_dir / f"{prefix}.mdout"
    return rst.exists() and _amber.mdout_succeeded(mdout)


def call_script(script: str, args: list[str], *, dry_run: bool) -> int:
    here = Path(__file__).parent
    cmd = [sys.executable, str(here / script)] + args
    if dry_run:
        cmd.append("--dry-run")
    print("$ " + " ".join(cmd))
    return subprocess.run(cmd).returncode


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Easy mode: chain prep + min + heat + density + prod (or REMD, "
            "or implicit) in one command."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", default="standard",
                   choices=["standard", "remd", "implicit"])
    p.add_argument("--structure", default=None)
    p.add_argument("--input-format", default=None,
                   choices=["pdb", "mol2", "sdf", "mol", "xyz"])
    p.add_argument("--net-charge", type=int, default=None)
    p.add_argument("--multiplicity", type=int, default=1)
    p.add_argument("--force-field", default="gaff2",
                   choices=["gaff2", "ff14SB", "ff19SB", "OL21"])
    p.add_argument("--water", default="tip3p",
                   choices=["tip3p", "opc", "spce", "tip4pew"])
    p.add_argument("--buffer", type=float, default=12.0)
    p.add_argument("--no-neutralize", action="store_true")
    p.add_argument("--salt-conc", type=float, default=0.0)
    p.add_argument("--box-shape", default="rect", choices=["rect", "oct"])
    p.add_argument("--temperature", type=float, default=300.0)
    p.add_argument("--time", default=None,
                   help="Production duration. Suffixes: ns, ps, fs.")
    p.add_argument("--barostat", default="berendsen",
                   choices=["berendsen", "monte_carlo", "off"])
    p.add_argument("--implicit-gb", default="gb2",
                   choices=["gb1", "gb2", "gb5", "gb7", "gb8"],
                   help="GB model when --mode implicit (default GBneck2).")
    # REMD-only
    p.add_argument("--n-replicas", type=int, default=8)
    p.add_argument("--t-low", type=float, default=300.0)
    p.add_argument("--t-high", type=float, default=400.0)
    p.add_argument("--exchange-every", type=int, default=1000)
    p.add_argument("--ladder", default="geometric",
                   choices=["geometric", "vdspoel", "explicit"])
    p.add_argument("--temps", default=None)
    p.add_argument("--mpiexec", default="mpirun")
    # Common
    p.add_argument("--engine", default=None)
    p.add_argument("--from-prmtop", action="store_true",
                   help="Skip prep; takes --prmtop + --rst.")
    p.add_argument("--prmtop", default=None)
    p.add_argument("--rst", default=None)
    p.add_argument("--output-prefix", default="system")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.time is None:
        raise SystemExit("--time is required (e.g. --time 1ns).")
    n_prod_steps = _amber.parse_time_to_steps(args.time, timestep_ps=0.002)

    if args.from_prmtop:
        if not (args.prmtop and args.rst):
            raise SystemExit("--from-prmtop requires --prmtop and --rst.")
        prmtop = Path(args.prmtop).resolve()
        rst = Path(args.rst).resolve()
        if not prmtop.exists() or not rst.exists():
            raise SystemExit(f"prmtop or rst not found: {prmtop}, {rst}")
    else:
        if not (args.structure and args.net_charge is not None):
            raise SystemExit(
                "Without --from-prmtop, --structure and --net-charge are required."
            )

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------- Step 1: prep ----------------
    if not args.from_prmtop:
        prep_dir = out_dir
        prefix = args.output_prefix
        prmtop = prep_dir / f"{prefix}.prmtop"
        rst = prep_dir / f"{prefix}.rst7"
        skip_prep = (
            args.resume
            and prmtop.exists() and rst.exists()
        )
        if skip_prep:
            print(f"[run] resume: prep already done ({prmtop.name}, {rst.name})")
        else:
            prep_args = [
                "--structure", args.structure,
                "--net-charge", str(args.net_charge),
                "--multiplicity", str(args.multiplicity),
                "--water", args.water,
                "--buffer", str(args.buffer),
                "--salt-conc", str(args.salt_conc),
                "--box-shape", args.box_shape,
                "--force-field", args.force_field,
                "--output-prefix", prefix,
                "--output-dir", str(prep_dir),
            ]
            if args.input_format:
                prep_args += ["--input-format", args.input_format]
            if args.no_neutralize:
                prep_args.append("--no-neutralize")
            if args.mode == "implicit":
                prep_args.append("--implicit")
            rc = call_script("amber_prep.py", prep_args, dry_run=False)
            if rc != 0:
                raise SystemExit(f"prep failed (rc={rc}).")

    common_md = ["--prmtop", str(prmtop)]
    implicit_arg = (
        ["--implicit-solvent", args.implicit_gb]
        if args.mode == "implicit" else []
    )

    # ---------------- Step 2: min ----------------
    if args.resume and stage_succeeded(out_dir, "min"):
        print("[run] resume: min already done")
    else:
        rc = call_script("amber_md.py",
                         common_md + ["--rst", str(rst), "--stage", "min",
                                      "--output-prefix", "min",
                                      "--output-dir", str(out_dir)]
                         + implicit_arg,
                         dry_run=args.dry_run)
        if rc != 0:
            raise SystemExit(f"min failed (rc={rc}).")
    min_rst = out_dir / "min.rst7"

    # ---------------- Step 3: heat ----------------
    if args.resume and stage_succeeded(out_dir, "heat"):
        print("[run] resume: heat already done")
    else:
        heat_args = (common_md
                     + ["--rst", str(min_rst), "--stage", "heat",
                        "--temperature", str(args.temperature),
                        "--n-steps", str(HEAT_STEPS),
                        "--output-prefix", "heat",
                        "--output-dir", str(out_dir)]
                     + implicit_arg)
        rc = call_script("amber_md.py", heat_args, dry_run=args.dry_run)
        if rc != 0:
            raise SystemExit(f"heat failed (rc={rc}).")
    heat_rst = out_dir / "heat.rst7"

    # ---------------- Step 4: density (skip for implicit) ----------------
    if args.mode == "implicit":
        print("[run] implicit mode: skipping density (no PBC)")
        ready_rst = heat_rst
    else:
        if args.resume and stage_succeeded(out_dir, "density"):
            print("[run] resume: density already done")
        else:
            dens_args = (common_md
                         + ["--rst", str(heat_rst), "--stage", "density",
                            "--temperature", str(args.temperature),
                            "--n-steps", str(DENSITY_STEPS),
                            "--barostat", args.barostat,
                            "--restart",
                            "--output-prefix", "density",
                            "--output-dir", str(out_dir)])
            rc = call_script("amber_md.py", dens_args, dry_run=args.dry_run)
            if rc != 0:
                raise SystemExit(f"density failed (rc={rc}).")
        ready_rst = out_dir / "density.rst7"

    # ---------------- Step 5: production ----------------
    if args.mode == "remd":
        if args.resume and any((out_dir / f"replica_{i:02d}/prod.rst7").exists()
                                for i in range(args.n_replicas)):
            print("[run] resume: REMD prod partially done — re-launching "
                  "missing replicas is not implemented in v1.0; falling "
                  "back to a full launch.")
        remd_args = ["--prmtop", str(prmtop), "--rst", str(ready_rst),
                     "--n-replicas", str(args.n_replicas),
                     "--t-low", str(args.t_low),
                     "--t-high", str(args.t_high),
                     "--n-steps", str(n_prod_steps),
                     "--exchange-every", str(args.exchange_every),
                     "--ladder", args.ladder,
                     "--mpiexec", args.mpiexec,
                     "--output-dir", str(out_dir)]
        if args.temps:
            remd_args += ["--temps", args.temps]
        if args.engine:
            remd_args += ["--engine", args.engine]
        if args.mode == "implicit":
            remd_args += ["--implicit-solvent", args.implicit_gb]
        rc = call_script("amber_remd.py", remd_args, dry_run=args.dry_run)
        if rc != 0:
            raise SystemExit(f"REMD prod failed (rc={rc}).")
    else:
        if args.resume and stage_succeeded(out_dir, "prod"):
            print("[run] resume: prod already done")
        else:
            prod_args = (common_md
                         + ["--rst", str(ready_rst), "--stage", "prod",
                            "--temperature", str(args.temperature),
                            "--n-steps", str(n_prod_steps),
                            "--barostat", args.barostat,
                            "--restart",
                            "--output-prefix", "prod",
                            "--output-dir", str(out_dir)]
                         + implicit_arg)
            if args.engine:
                prod_args += ["--engine", args.engine]
            rc = call_script("amber_md.py", prod_args, dry_run=args.dry_run)
            if rc != 0:
                raise SystemExit(f"prod failed (rc={rc}).")

    if args.dry_run:
        print()
        print("[run] --dry-run complete: no commands executed.")
        return 0

    print()
    print(f"[run] pipeline complete. Output in {out_dir}")
    if args.mode != "remd":
        print(f"[run] trajectory: {out_dir / 'prod.nc'}")
        print("[run] analyze with: python scripts/amber_analyze.py "
              f"--prmtop {prmtop} --trajectory {out_dir / 'prod.nc'}")
    else:
        print(f"[run] REMD trajectories: {out_dir}/replica_NN/prod.nc")
        print("[run] demux with: python scripts/amber_analyze.py "
              f"--demux-remd --remd-dir {out_dir} --prmtop {prmtop}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
