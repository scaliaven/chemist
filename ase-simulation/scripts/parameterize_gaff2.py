#!/usr/bin/env python3
"""Parameterize a small organic molecule with GAFF2 + AM1-BCC charges.

When to use:
    The user has a small organic molecule (≤ ~150 atoms; drug-like or
    cofactor-like) and needs to run explicit-solvent MD on it. This
    script drives `antechamber -c bcc -s 2` to assign AM1-BCC partial
    charges, then `parmchk2` for missing GAFF2 parameters, then
    `tleap` for solvation in a TIP3P or OPC box with neutralizing
    counter-ions. Output is the `.prmtop` / `.rst7` pair that
    `run_amber.py` consumes.

When NOT to use:
    Proteins or nucleic acids — those use ff19SB+OPC / OL21 and need
    pdb4amber / different tleap leaprc files. Protein/NA support is
    deferred to v2.3; do not adapt this script for it.
    Already-parameterized systems (you have `.prmtop` and `.rst7`)
    skip directly to `run_amber.py`.
    Charged species where you don't know the formal charge — antechamber
    will silently use 0 if you don't pass `--net-charge`. Wrong.

Examples:
    # Parameterize caffeine (neutral, .pdb), default TIP3P box
    python parameterize_gaff2.py --structure caffeine.pdb \\
        --net-charge 0 --output-prefix caffeine

    # Aspirin in OPC water with a 14 Å buffer
    python parameterize_gaff2.py --structure aspirin.mol2 \\
        --input-format mol2 --net-charge 0 --water opc \\
        --buffer 14.0 --output-prefix aspirin

Outputs (in --output-dir):
    <prefix>.prmtop          Amber topology
    <prefix>.rst7            initial coordinates with periodic box
    <prefix>_solvated.pdb    PDB of the solvated system (for visualization)
    <prefix>.frcmod          parmchk2 output, kept for inspection
    <prefix>.mol2            antechamber output, kept for inspection
    tleap.in / tleap.log     tleap script and log
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_BINARIES = ("antechamber", "parmchk2", "tleap")


def check_binaries() -> None:
    missing = [b for b in REQUIRED_BINARIES if shutil.which(b) is None]
    if missing:
        raise SystemExit(
            f"AmberTools binaries missing from PATH: {', '.join(missing)}\n"
            "Install AmberTools (free): https://ambermd.org/GetAmber.php\n"
            "Run scripts/check_env.py to see broader Amber detection status."
        )


def infer_input_format(path: Path, override: str | None) -> str:
    if override:
        return override
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("pdb", "mol2", "sdf", "mol", "xyz"):
        # antechamber -fi accepts these directly.
        return suffix
    raise SystemExit(
        f"Cannot infer input format from extension '{path.suffix}'. "
        f"Pass --input-format explicitly (pdb, mol2, sdf, mol, xyz)."
    )


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=cwd).returncode
    if rc != 0:
        raise SystemExit(f"Command failed (rc={rc}): {' '.join(cmd)}")


def write_tleap_script(path: Path, *, prefix: str, mol2: Path,
                       frcmod: Path, water: str, buffer_a: float,
                       neutralize: bool) -> None:
    """Render the tleap input deck.

    Conservative defaults: neutralizing Na+/Cl- only (no extra salt
    concentration), rectangular box (truncated octahedron is supported
    by tleap but rejected by ASE's Amber calculator path; v2.2 uses
    shell-out to pmemd so this is no longer a constraint, but we keep
    the simpler box for predictable analyze_traj.py behaviour).
    """
    if water == "tip3p":
        leaprc_water = "leaprc.water.tip3p"
        solvent_box = "TIP3PBOX"
    elif water == "opc":
        leaprc_water = "leaprc.water.opc"
        solvent_box = "OPCBOX"
    else:
        raise SystemExit(f"Unknown water model: {water}")

    lines = [
        "source leaprc.gaff2",
        f"source {leaprc_water}",
        f"LIG = loadmol2 {mol2.name}",
        f"loadamberparams {frcmod.name}",
        f"solvateBox LIG {solvent_box} {buffer_a:.2f}",
    ]
    if neutralize:
        lines += [
            "addions LIG Na+ 0",
            "addions LIG Cl- 0",
        ]
    lines += [
        f"saveAmberParm LIG {prefix}.prmtop {prefix}.rst7",
        f"savePdb LIG {prefix}_solvated.pdb",
        "quit",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parameterize a small organic molecule with GAFF2 + AM1-BCC "
            "charges, solvate in TIP3P/OPC with neutralizing ions, and "
            "write the .prmtop / .rst7 pair consumed by run_amber.py."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--structure", required=True,
                   help="Input structure (pdb / mol2 / sdf / mol / xyz).")
    p.add_argument("--input-format", default=None,
                   choices=["pdb", "mol2", "sdf", "mol", "xyz"],
                   help="Override format inferred from extension.")
    p.add_argument("--net-charge", type=int, required=True,
                   help="Net integer charge of the molecule. AM1-BCC "
                        "needs this to assign charges correctly; getting "
                        "it wrong silently shifts every partial charge.")
    p.add_argument("--multiplicity", type=int, default=1,
                   help="Spin multiplicity (rarely matters for closed-shell "
                        "organics; antechamber assumes 1 by default).")
    p.add_argument("--water", default="tip3p", choices=["tip3p", "opc"],
                   help="Water model. TIP3P is GAFF2's calibration target; "
                        "OPC is a more accurate 4-site model that pairs "
                        "well with ff19SB but is fine with GAFF2 too.")
    p.add_argument("--buffer", type=float, default=12.0,
                   help="Solvent buffer in Å around the solute. 12 Å is "
                        "the AmberMD tutorial standard; 14 Å is safer for "
                        "long runs.")
    p.add_argument("--no-neutralize", action="store_true",
                   help="Skip neutralizing counter-ions. Default adds the "
                        "minimum Na+/Cl- needed to neutralize.")
    p.add_argument("--output-prefix", default="system",
                   help="Prefix for output files in --output-dir.")
    p.add_argument("--output-dir", default=".",
                   help="Directory where intermediates and outputs land.")
    p.add_argument("--keep-intermediates", action="store_true",
                   help="Keep antechamber's .ac / .sqm scratch files.")
    args = p.parse_args()

    check_binaries()

    src = Path(args.structure).resolve()
    if not src.exists():
        raise SystemExit(f"Input structure not found: {src}")

    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt = infer_input_format(src, args.input_format)
    prefix = args.output_prefix
    mol2 = out_dir / f"{prefix}.mol2"
    frcmod = out_dir / f"{prefix}.frcmod"
    tleap_in = out_dir / "tleap.in"
    tleap_log = out_dir / "tleap.log"

    print(f"[gaff2] input        : {src}")
    print(f"[gaff2] format       : {fmt}")
    print(f"[gaff2] net charge   : {args.net_charge}")
    print(f"[gaff2] water model  : {args.water}")
    print(f"[gaff2] buffer       : {args.buffer} Å")
    print(f"[gaff2] output dir   : {out_dir}")
    print(f"[gaff2] prefix       : {prefix}")
    print()

    # 1) antechamber: assign AM1-BCC charges, write GAFF2-typed mol2
    antechamber_cmd = [
        "antechamber",
        "-i", str(src),
        "-fi", fmt,
        "-o", str(mol2),
        "-fo", "mol2",
        "-c", "bcc",
        "-s", "2",
        "-nc", str(args.net_charge),
        "-m", str(args.multiplicity),
        "-at", "gaff2",
    ]
    run(antechamber_cmd, cwd=out_dir)

    # 2) parmchk2: write missing-parameters frcmod
    parmchk_cmd = [
        "parmchk2", "-i", str(mol2), "-f", "mol2", "-o", str(frcmod),
        "-s", "gaff2",
    ]
    run(parmchk_cmd, cwd=out_dir)

    # 3) tleap: solvate, neutralize, save prmtop/rst7
    write_tleap_script(
        tleap_in, prefix=prefix, mol2=mol2, frcmod=frcmod,
        water=args.water, buffer_a=args.buffer,
        neutralize=not args.no_neutralize,
    )
    tleap_cmd = ["tleap", "-f", str(tleap_in.name)]
    with tleap_log.open("w") as fh:
        print(f"$ tleap -f {tleap_in.name}  > {tleap_log}")
        rc = subprocess.run(tleap_cmd, cwd=out_dir, stdout=fh,
                            stderr=subprocess.STDOUT).returncode
    if rc != 0:
        raise SystemExit(
            f"tleap failed (rc={rc}). Inspect {tleap_log} — common causes: "
            "missing GAFF2 atom types, antechamber failed silently, "
            "incompatible mol2 connectivity. Re-run with "
            "--keep-intermediates to inspect the scratch files."
        )

    prmtop = out_dir / f"{prefix}.prmtop"
    rst7 = out_dir / f"{prefix}.rst7"
    if not (prmtop.exists() and rst7.exists()):
        raise SystemExit(
            f"tleap reported success but {prmtop.name}/{rst7.name} are "
            f"missing. Inspect {tleap_log}."
        )

    if not args.keep_intermediates:
        for stem in ("sqm.in", "sqm.out", "sqm.pdb", "ANTECHAMBER_AC.AC",
                     "ANTECHAMBER_AC.AC0", "ANTECHAMBER_BOND_TYPE.AC",
                     "ANTECHAMBER_BOND_TYPE.AC0",
                     "ANTECHAMBER_AM1BCC.AC",
                     "ANTECHAMBER_AM1BCC_PRE.AC", "ATOMTYPE.INF",
                     "leap.log"):
            f = out_dir / stem
            if f.exists():
                f.unlink()

    print()
    print(f"[gaff2] wrote {prmtop}")
    print(f"[gaff2] wrote {rst7}")
    print(f"[gaff2] wrote {out_dir / (prefix + '_solvated.pdb')}")
    print()
    print("Next: run MD via")
    print(f"  python scripts/run_amber.py --prmtop {prmtop} --rst {rst7} \\")
    print(f"      --protocol standard --output-dir {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
