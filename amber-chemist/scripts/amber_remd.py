#!/usr/bin/env python3
"""Run Temperature Replica-Exchange MD (T-REMD) via pmemd.cuda.MPI -rem 1.

When to use:
    The user wants enhanced sampling on a small system (peptide,
    ligand, conformational ensemble) and is willing to pay for N
    parallel replicas to escape kinetic traps. T-REMD is the standard
    enhanced-sampling method shipped here in v1.0.

When NOT to use:
    Single-replica MD — use amber_md.py instead.
    Hamiltonian REMD (different lambda per replica) — pre-wired via
    --type H but raises NotImplementedError in v1.0.
    Free energy (TI / FEP / MBAR) — out of scope; see
    references/extension_map.md.

Engine:
    Auto-picks pmemd.cuda.MPI > pmemd.MPI > sander.MPI. Override with
    --engine. Auto-fail with a clear message if no MPI engine is on
    PATH.

Output layout:
    <output-dir>/
        groupfile                 # one line per replica
        rem.log                   # exchange log written by pmemd
        ladder.txt                # the temperature ladder
        exchange_rate.txt         # parsed acceptance rates
        replica_00/{prod.in, prod.mdout, prod.nc, prod.rst7}
        replica_01/...

After the run, this script prints per-pair acceptance rates parsed
from rem.log. Rates outside [15%, 50%] mean the ladder is mistuned.
See references/remd.md for tuning guidance.

Demux into per-temperature trajectories is handled by
`amber_analyze.py --demux-remd --remd-dir <output-dir>` so users only
pay for it when needed.

Examples:
    # 8 replicas, 300-400 K, 1 ns per replica
    python amber_remd.py --prmtop sys.prmtop --rst sys.rst7 \\
        --n-replicas 8 --t-low 300 --t-high 400 \\
        --n-steps 500000 --exchange-every 1000 \\
        --output-dir remd_out/

    # Explicit ladder
    python amber_remd.py --prmtop sys.prmtop --rst sys.rst7 \\
        --n-replicas 6 --ladder explicit \\
        --temps "300,310,322,335,350,367" \\
        --output-dir remd_out/
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Temperature Replica-Exchange MD via pmemd.cuda.MPI -rem 1. "
            "Auto temperature ladder, groupfile, exchange-rate report."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--prmtop", required=True)
    p.add_argument("--rst", required=True)
    p.add_argument("--n-replicas", type=int, required=True)
    p.add_argument("--type", default="T", choices=["T", "H"],
                   help="T = temperature REMD (v1.0). H = Hamiltonian REMD "
                        "(v1.1+ — raises today).")
    p.add_argument("--t-low", type=float, default=300.0)
    p.add_argument("--t-high", type=float, default=400.0)
    p.add_argument("--ladder", default="geometric",
                   choices=["geometric", "vdspoel", "explicit"])
    p.add_argument("--temps", default=None,
                   help="Comma-separated temperatures (only with --ladder explicit).")
    p.add_argument("--n-steps", type=int, default=250000,
                   help="MD steps per exchange interval times numexchg. "
                        "v1.0 uses nstlim=exchange-every and "
                        "numexchg=n-steps/exchange-every.")
    p.add_argument("--exchange-every", type=int, default=1000,
                   help="Steps between exchange attempts.")
    p.add_argument("--timestep", type=float, default=0.002)
    p.add_argument("--cut", type=float, default=10.0)
    p.add_argument("--gamma-ln", type=float, default=2.0)
    p.add_argument("--implicit-solvent", default="off",
                   choices=["off", "gb1", "gb2", "gb5", "gb7", "gb8"])
    p.add_argument("--engine", default=None,
                   help="MPI engine override (pmemd.cuda.MPI / pmemd.MPI / sander.MPI).")
    p.add_argument("--mpiexec", default="mpirun",
                   help="MPI launcher (e.g. mpirun, srun, mpiexec).")
    p.add_argument("--output-prefix", default="prod")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.type == "H":
        raise NotImplementedError(
            "Hamiltonian REMD is a v1.1+ pre-wired hook. v1.0 ships "
            "T-REMD only. See references/extension_map.md."
        )

    prmtop = Path(args.prmtop).resolve()
    rst = Path(args.rst).resolve()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        if not prmtop.exists():
            raise SystemExit(f"prmtop not found: {prmtop}")
        if not rst.exists():
            raise SystemExit(f"input rst7 not found: {rst}")

    if args.exchange_every < 100:
        print(f"[remd] WARNING: --exchange-every={args.exchange_every} is "
              "unusually low; pmemd guidance is ~500-2000 steps between "
              "attempts.")
    if args.n_steps % args.exchange_every != 0:
        raise SystemExit(
            f"--n-steps ({args.n_steps}) must be a multiple of "
            f"--exchange-every ({args.exchange_every})."
        )
    numexchg = args.n_steps // args.exchange_every

    explicit = None
    if args.temps is not None:
        explicit = [float(t) for t in args.temps.split(",")]

    if args.ladder == "vdspoel":
        print("[remd] NOTE: --ladder vdspoel falls back to geometric in "
              "v1.0; full Patriksson-van der Spoel iterative solver is a "
              "v1.1 candidate.")

    temps = _amber.build_temperature_ladder(
        args.n_replicas,
        t_low=args.t_low, t_high=args.t_high,
        ladder=args.ladder, explicit=explicit,
    )

    # Spread sanity: warn if any pair-gap exceeds 50 K (acceptance will be poor).
    gaps = [temps[i + 1] - temps[i] for i in range(len(temps) - 1)]
    max_gap = max(gaps)
    if max_gap > 50.0:
        print(f"[remd] WARNING: largest temperature gap is {max_gap:.1f} K; "
              "exchange acceptance will likely be < 15%. Consider more "
              "replicas or a narrower range. See references/remd.md.")

    ladder_txt = out_dir / "ladder.txt"
    ladder_txt.write_text(
        "\n".join(f"{i:02d}\t{t:.2f}" for i, t in enumerate(temps)) + "\n"
    )

    if args.dry_run and shutil.which(args.engine or "pmemd.cuda.MPI") is None:
        engine = args.engine or "pmemd.cuda.MPI"
        engine_note = " (placeholder — dry-run, not on PATH)"
    else:
        engine = _amber.pick_engine(args.engine, need_mpi=True)
        engine_note = ""
    implicit_gb = {"off": 0, "gb1": 1, "gb2": 2,
                   "gb5": 5, "gb7": 7, "gb8": 8}[args.implicit_solvent]

    print(f"[remd] engine        : {engine}{engine_note}")
    print(f"[remd] mpiexec       : {args.mpiexec}")
    print(f"[remd] n_replicas    : {args.n_replicas}")
    print(f"[remd] ladder        : {args.ladder}")
    print(f"[remd] temperatures  : {', '.join(f'{t:.1f}' for t in temps)}")
    print(f"[remd] exchange_every: {args.exchange_every}")
    print(f"[remd] numexchg      : {numexchg}")
    print(f"[remd] total ps      : {args.n_steps * args.timestep:.1f}")
    print(f"[remd] output_dir    : {out_dir}")
    print()

    # Per-replica mdin
    for i, temp in enumerate(temps):
        rep_dir = out_dir / f"replica_{i:02d}"
        rep_dir.mkdir(parents=True, exist_ok=True)
        mdin_text = _amber.render_prod(
            temp=temp,
            n_steps=args.exchange_every,
            timestep=args.timestep,
            cut=args.cut,
            gamma_ln=args.gamma_ln,
            barostat="off",  # REMD typically NVT in pmemd's -rem 1 mode
            write_every=args.exchange_every,
            implicit_gb=implicit_gb,
            irest=False,
            remd=True,
            numexchg=numexchg,
        )
        (rep_dir / f"{args.output_prefix}.in").write_text(mdin_text)

    groupfile = out_dir / "groupfile"
    _amber.write_groupfile(
        groupfile,
        n_replicas=args.n_replicas,
        base_dir=out_dir,
        mdin_name=f"{args.output_prefix}.in",
        rst_name=f"{args.output_prefix}.rst7",
        out_rst_name=f"{args.output_prefix}.rst7",
        out_mdout=f"{args.output_prefix}.mdout",
        out_nc=f"{args.output_prefix}.nc",
        initial_rst=rst,
    )

    cmd = [
        args.mpiexec, "-np", str(args.n_replicas),
        engine, "-ng", str(args.n_replicas),
        "-groupfile", str(groupfile),
        "-rem", "1",
        "-remlog", str(out_dir / "rem.log"),
    ]
    rc = _amber.run_cmd(cmd, cwd=out_dir, dry_run=args.dry_run)

    if args.dry_run:
        print()
        print("[remd] --dry-run: no execution. Inspect groupfile and "
              "per-replica mdin under replica_NN/.")
        return 0
    if rc != 0:
        raise SystemExit(
            f"{engine} REMD failed (rc={rc}). Inspect "
            f"{out_dir / 'rem.log'} and per-replica mdout files."
        )

    # Exchange-rate report
    rows = _amber.parse_remlog(out_dir / "rem.log")
    rate_lines: list[str] = []
    if rows:
        for r in rows:
            rate_lines.append(
                f"  pair {r['i']:02d}<->{r['j']:02d}: "
                f"attempts={r['attempts']} accepts={r['accepts']} "
                f"rate={r['rate']:.1f}%"
            )
        all_rates = [r["rate"] for r in rows]
        outside = [r for r in all_rates if r < 15.0 or r > 50.0]
        recommendation = (
            "OK — all exchange rates within the 15-50% window."
            if not outside
            else f"{len(outside)}/{len(all_rates)} pairs outside [15%, 50%]; "
                 "consider re-tuning the ladder. See references/remd.md."
        )
    else:
        rate_lines.append("  (could not parse rem.log; format may have changed)")
        recommendation = "Could not parse exchange rates — inspect rem.log manually."

    report = (
        "T-REMD exchange-rate report\n"
        + "\n".join(rate_lines) + "\n"
        + recommendation + "\n"
    )
    (out_dir / "exchange_rate.txt").write_text(report)
    print()
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
