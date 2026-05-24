#!/usr/bin/env python3
"""Run a single stage of Amber MD: min / heat / density / prod / custom.

When to use:
    You have a .prmtop + .rst7 pair (from amber_prep.py or anywhere
    else — CHARMM-GUI, an existing project) and you want to run one
    stage of MD: minimization, heating, density equilibration,
    production NPT or NVT, or a fully custom mdin you wrote yourself.

    This is the load-bearing v1.0 verb. amber_run.py chains stages for
    you; reach for amber_md.py when you want stage-level control.

When NOT to use:
    REMD — use amber_remd.py.
    Endpoint binding free energy — use amber_score.py on a finished
    trajectory.

Stages:
    min        Minimization (imin=1, maxcyc, ncyc, optional restraints).
    heat       NVT thermalization 0 -> T over n-steps (SHAKE on H).
    density    NPT density equilibration (Berendsen / MC barostat).
    prod       NPT or implicit-GB production MD.
    custom     Pass your own mdin via --mdin.

Restart vs extend:
    --restart flips the deck to irest=1, ntx=5 (chains stages, e.g.
    heat -> density). It is read from the input rst7 you pass in.

    --extend chains chunks of the SAME stage. If <prefix>.rst7 already
    exists alongside a successful <prefix>.mdout, the next chunk is
    written as <prefix>_2.{nc,rst7,mdout}, then _3, etc. Use this for
    "run another N ps of prod from where I left off."

Examples:
    # Minimization, then heat (chained via --restart)
    python amber_md.py --prmtop sys.prmtop --rst sys.rst7 --stage min \\
        --output-prefix min --output-dir run/
    python amber_md.py --prmtop sys.prmtop --rst run/min.rst7 \\
        --stage heat --restart --output-prefix heat --output-dir run/

    # Production NPT with Monte Carlo barostat, 5 ns
    python amber_md.py --prmtop sys.prmtop --rst run/density.rst7 \\
        --stage prod --restart --barostat monte_carlo --n-steps 2500000 \\
        --output-prefix prod --output-dir run/

    # Extend a finished prod by another 2 ns
    python amber_md.py --prmtop sys.prmtop --rst run/prod.rst7 \\
        --stage prod --extend --n-steps 1000000 \\
        --output-prefix prod --output-dir run/

    # Implicit-solvent (OBC model I, igb=2) production
    python amber_md.py --prmtop sys.prmtop --rst sys.rst7 \\
        --stage prod --implicit-solvent gb2 --n-steps 2500000 \\
        --output-prefix prod --output-dir run/
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402
from _amber import GB_MAP  # noqa: E402


def find_extend_target(out_dir: Path, prefix: str) -> tuple[Path, str]:
    """Pick the next available extend chunk: <prefix>_2, _3, ...

    Returns (input_rst, new_prefix). If the base <prefix>.rst7 has a
    successful mdout, start at _2; otherwise the user should not be
    using --extend and we raise.
    """
    base_rst = out_dir / f"{prefix}.rst7"
    base_mdout = out_dir / f"{prefix}.mdout"
    if not (base_rst.exists() and _amber.mdout_succeeded(base_mdout)):
        raise SystemExit(
            f"--extend needs a finished {prefix}.{{rst7,mdout}} in "
            f"{out_dir}. Found rst7={base_rst.exists()}, "
            f"mdout-success={_amber.mdout_succeeded(base_mdout)}. "
            "Use --restart to chain a different stage instead."
        )
    i = 2
    while True:
        chunk_rst = out_dir / f"{prefix}_{i}.rst7"
        chunk_mdout = out_dir / f"{prefix}_{i}.mdout"
        if not chunk_rst.exists():
            return base_rst if i == 2 else out_dir / f"{prefix}_{i - 1}.rst7", \
                   f"{prefix}_{i}"
        if not _amber.mdout_succeeded(chunk_mdout):
            return out_dir / f"{prefix}_{i - 1}.rst7" if i > 2 else base_rst, \
                   f"{prefix}_{i}"
        i += 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Run one stage of Amber MD: min, heat, density, prod, or "
            "custom (with --mdin). Restart-and-extend aware."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--prmtop", required=True)
    p.add_argument("--rst", required=True,
                   help="Input coordinates (.rst7 or .inpcrd).")
    p.add_argument("--stage", required=True,
                   choices=["min", "heat", "density", "prod", "custom"])
    p.add_argument("--temperature", type=float, default=300.0)
    p.add_argument("--n-steps", type=int, default=None,
                   help="Override stage default (heat=25000, density=50000, "
                        "prod=250000). Ignored for min (use --maxcyc).")
    p.add_argument("--maxcyc", type=int, default=10000)
    p.add_argument("--ncyc", type=int, default=5000)
    p.add_argument("--timestep", type=float, default=0.002,
                   help="MD timestep in ps.")
    p.add_argument("--cut", type=float, default=10.0,
                   help="Nonbonded cutoff in Å (ignored for implicit GB).")
    p.add_argument("--gamma-ln", type=float, default=2.0,
                   help="Langevin friction in 1/ps.")
    p.add_argument("--barostat", default="berendsen",
                   choices=["berendsen", "monte_carlo", "off"])
    p.add_argument("--restart", action="store_true",
                   help="Chain from a previous stage's rst7 (irest=1, ntx=5).")
    p.add_argument("--extend", action="store_true",
                   help="Chain another chunk of the SAME stage. "
                        "Auto-numbers _2, _3, ...")
    p.add_argument("--restraint-mask", default=None,
                   help="Amber mask for positional restraints, e.g. "
                        "':1-200&!@H='.")
    p.add_argument("--restraint-weight", type=float, default=10.0,
                   help="Restraint force constant in kcal/mol/Å².")
    p.add_argument("--ref", default=None,
                   help="Reference rst7 for positional restraints "
                        "(passed via -ref to the engine).")
    p.add_argument("--write-every", type=int, default=500,
                   help="Trajectory write frequency (ntwx).")
    p.add_argument("--implicit-solvent", default="off",
                   choices=list(GB_MAP),
                   help="Implicit GB model. off=explicit; gb2=OBC model I; gb8=GBneck2.")
    p.add_argument("--engine", default=None,
                   help="Engine override (pmemd.cuda / pmemd / sander).")
    p.add_argument("--mdin", default=None,
                   help="User-supplied mdin file (only for --stage custom).")
    p.add_argument("--output-prefix", default=None,
                   help="Defaults to the stage name.")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--dry-run", action="store_true",
                   help="Render mdin and print the engine command; do not "
                        "execute.")
    args = p.parse_args()

    if args.stage == "custom" and not args.mdin:
        raise SystemExit("--stage custom requires --mdin <file>.")
    if args.restart and args.extend:
        raise SystemExit("--restart and --extend are mutually exclusive.")

    prmtop = Path(args.prmtop).resolve()
    rst = Path(args.rst).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        if not prmtop.exists():
            raise SystemExit(f"prmtop not found: {prmtop}")
        if not rst.exists():
            raise SystemExit(f"input rst7 not found: {rst}")

    prefix = args.output_prefix or args.stage
    if args.extend:
        rst, prefix = find_extend_target(out_dir, prefix)
        print(f"[md] --extend: chunk -> {prefix} (input rst = {rst.name})")

    if args.dry_run and shutil.which(args.engine or "pmemd.cuda") is None:
        engine = args.engine or "pmemd.cuda"
        print(f"[md] engine     : {engine} (placeholder — dry-run, not on PATH)")
    else:
        engine = _amber.pick_engine(args.engine)
        print(f"[md] engine     : {engine}")
    print(f"[md] stage      : {args.stage}")
    print(f"[md] prmtop     : {prmtop}")
    print(f"[md] start rst  : {rst}")
    print(f"[md] output     : {out_dir}/{prefix}.{{mdin,mdout,rst7,nc}}")
    print(f"[md] target T   : {args.temperature} K")
    print(f"[md] implicit   : {args.implicit_solvent}")
    print()

    implicit_gb = GB_MAP[args.implicit_solvent]
    timestep = args.timestep

    # Render mdin per stage. `custom` stage takes the user's file as-is.
    if args.stage == "custom":
        mdin_text = Path(args.mdin).read_text()
    elif args.stage == "min":
        mdin_text = _amber.render_min(
            maxcyc=args.maxcyc, ncyc=args.ncyc, cut=args.cut,
            restraint_mask=args.restraint_mask,
            restraint_weight=args.restraint_weight,
            implicit_gb=implicit_gb,
        )
    elif args.stage == "heat":
        n_steps = args.n_steps if args.n_steps is not None else 25000
        mdin_text = _amber.render_heat(
            temp=args.temperature, n_steps=n_steps, timestep=timestep,
            cut=args.cut, gamma_ln=args.gamma_ln,
            write_every=args.write_every,
            restraint_mask=args.restraint_mask,
            restraint_weight=args.restraint_weight,
            implicit_gb=implicit_gb,
        )
    elif args.stage == "density":
        if implicit_gb:
            raise SystemExit(
                "--stage density is meaningless for implicit-solvent MD "
                "(no PBC). Skip density and go straight to prod with "
                "--implicit-solvent."
            )
        n_steps = args.n_steps if args.n_steps is not None else 50000
        mdin_text = _amber.render_density(
            temp=args.temperature, n_steps=n_steps, timestep=timestep,
            cut=args.cut, gamma_ln=args.gamma_ln,
            barostat=args.barostat,
            write_every=args.write_every,
            restraint_mask=args.restraint_mask,
            restraint_weight=args.restraint_weight,
        )
    elif args.stage == "prod":
        n_steps = args.n_steps if args.n_steps is not None else 250000
        mdin_text = _amber.render_prod(
            temp=args.temperature, n_steps=n_steps, timestep=timestep,
            cut=args.cut, gamma_ln=args.gamma_ln,
            barostat=args.barostat,
            write_every=args.write_every,
            restraint_mask=args.restraint_mask,
            restraint_weight=args.restraint_weight,
            implicit_gb=implicit_gb,
            irest=args.restart or args.extend,
        )

    mdin = out_dir / f"{prefix}.in"
    mdout = out_dir / f"{prefix}.mdout"
    out_rst = out_dir / f"{prefix}.rst7"
    out_nc = out_dir / f"{prefix}.nc"
    if not args.dry_run:
        mdin.write_text(mdin_text)
    else:
        print(f"--- mdin ({mdin}) ---")
        print(mdin_text)

    cmd = [
        engine, "-O",
        "-i", str(mdin),
        "-o", str(mdout),
        "-p", str(prmtop),
        "-c", str(rst),
        "-r", str(out_rst),
        "-x", str(out_nc),
    ]
    if args.ref:
        cmd += ["-ref", str(Path(args.ref).resolve())]

    rc = _amber.run_cmd(cmd, dry_run=args.dry_run)
    if rc != 0:
        raise SystemExit(f"{engine} failed (rc={rc}). Inspect {mdout}.")
    if not args.dry_run and not out_rst.exists():
        raise SystemExit(
            f"{engine} reported success but {out_rst} is missing."
        )

    if not args.dry_run:
        print()
        print(f"[md] wrote {out_rst}")
        print(f"[md] wrote {out_nc}")
        print(f"[md] wrote {mdout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
