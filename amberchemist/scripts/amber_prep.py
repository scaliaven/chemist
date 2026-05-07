#!/usr/bin/env python3
"""Parameterize a small organic molecule for Amber MD.

When to use:
    The user has a small organic molecule (≤ ~150 atoms; drug-like or
    cofactor-like) and needs to prepare it for explicit-solvent or
    implicit-solvent Amber MD. This script drives:

        antechamber -c bcc -s 2  ->  AM1-BCC partial charges + GAFF2 typing
        parmchk2                 ->  missing-parameter frcmod
        tleap                    ->  solvate (TIP3P/OPC/SPCE/TIP4P-Ew),
                                     neutralize, optionally add salt,
                                     write prmtop/rst7

When NOT to use:
    Proteins or nucleic acids — those want ff19SB+OPC / OL21 and are
    deferred to v1.1; --force-field {ff19SB, ff14SB, OL21} raises
    NotImplementedError today.
    Already-parameterized systems — pass --prmtop/--rst directly to
    amber_md.py instead.

Examples:
    # Caffeine, neutral, TIP3P, 12 Å buffer, ready for explicit MD
    python amber_prep.py --structure caffeine.pdb --net-charge 0 \\
        --output-prefix caffeine --output-dir prep/

    # Aspirin in OPC water, 14 Å buffer, with 0.15 M salt
    python amber_prep.py --structure aspirin.mol2 --input-format mol2 \\
        --net-charge 0 --water opc --buffer 14.0 --salt-conc 0.15 \\
        --output-prefix aspirin

    # Small molecule for implicit-solvent MD (no waterbox)
    python amber_prep.py --structure ligand.pdb --net-charge 0 \\
        --implicit --output-prefix ligand
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _amber  # noqa: E402


REQUIRED_BINARIES = ("antechamber", "parmchk2", "tleap")


def check_binaries() -> None:
    missing = [b for b in REQUIRED_BINARIES if shutil.which(b) is None]
    if missing:
        raise SystemExit(
            f"AmberTools binaries missing from PATH: {', '.join(missing)}\n"
            "Install AmberTools (free): https://ambermd.org/GetAmber.php\n"
            "Run scripts/check_env.py to see broader detection status."
        )


def infer_input_format(path: Path, override: str | None) -> str:
    if override:
        return override
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("pdb", "mol2", "sdf", "mol", "xyz"):
        return suffix
    raise SystemExit(
        f"Cannot infer input format from extension '{path.suffix}'. "
        f"Pass --input-format explicitly (pdb, mol2, sdf, mol, xyz)."
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parameterize a small organic molecule (GAFF2 + AM1-BCC), "
            "solvate (TIP3P/OPC/SPCE/TIP4P-Ew) or skip solvation for "
            "implicit-solvent MD, write the .prmtop / .rst7 pair "
            "consumed by amber_md.py / amber_remd.py."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--structure", required=True,
                   help="Input structure (pdb / mol2 / sdf / mol / xyz).")
    p.add_argument("--input-format", default=None,
                   choices=["pdb", "mol2", "sdf", "mol", "xyz"],
                   help="Override format inferred from extension.")
    p.add_argument("--net-charge", type=int, required=True,
                   help="Net integer charge of the molecule. Wrong value "
                        "silently shifts every partial charge.")
    p.add_argument("--multiplicity", type=int, default=1)
    p.add_argument("--force-field", default="gaff2",
                   choices=["gaff2", "ff14SB", "ff19SB", "OL21"],
                   help="GAFF2 ships in v1.0; biopolymer force fields "
                        "raise NotImplementedError.")
    p.add_argument("--charge-method", default="bcc",
                   choices=["bcc", "gas", "resp_external"],
                   help="bcc=AM1-BCC (default); gas=Gasteiger (toy only); "
                        "resp_external requires --resp-charges-file.")
    p.add_argument("--resp-charges-file", default=None,
                   help="External RESP charges file (v1.1+ — raises today).")
    p.add_argument("--protein-pdb", default=None,
                   help="Pre-wired flag for v1.1 complex prep — raises today.")
    p.add_argument("--ligand-pdb", default=None,
                   help="Pre-wired flag for v1.1 complex prep — raises today.")
    p.add_argument("--water", default="tip3p",
                   choices=["tip3p", "opc", "spce", "tip4pew"],
                   help="Water model (ignored when --implicit).")
    p.add_argument("--buffer", type=float, default=12.0,
                   help="Solvent buffer in Å around solute.")
    p.add_argument("--no-neutralize", action="store_true",
                   help="Skip neutralizing counter-ions.")
    p.add_argument("--salt-conc", type=float, default=0.0,
                   help="Approximate salt concentration in M (0 = neutralize only).")
    p.add_argument("--box-shape", default="rect",
                   choices=["rect", "oct"],
                   help="Rectangular or truncated octahedron box.")
    p.add_argument("--implicit", action="store_true",
                   help="Skip solvateBox / addions — system is for "
                        "implicit-solvent MD (igb=N).")
    p.add_argument("--output-prefix", default="system")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--keep-intermediates", action="store_true")
    args = p.parse_args()

    if args.force_field != "gaff2":
        raise NotImplementedError(
            f"v1.0 ships GAFF2 only; --force-field {args.force_field} is "
            "deferred to v1.1 (ff14SB/ff19SB/OL21). See "
            "references/extension_map.md and references/force_fields.md."
        )
    if args.charge_method == "resp_external":
        raise NotImplementedError(
            "v1.0 ships AM1-BCC and Gasteiger only; "
            "--charge-method resp_external is a v1.1+ pre-wired hook. "
            "See references/force_fields.md."
        )
    if args.protein_pdb or args.ligand_pdb:
        raise NotImplementedError(
            "Protein/ligand complex prep is a v1.1 pre-wired hook. "
            "v1.0 prepares one small molecule at a time. See "
            "references/extension_map.md."
        )

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

    print(f"[prep] input        : {src}")
    print(f"[prep] format       : {fmt}")
    print(f"[prep] net charge   : {args.net_charge}")
    print(f"[prep] charge method: {args.charge_method}")
    print(f"[prep] water model  : {args.water if not args.implicit else 'none (implicit)'}")
    print(f"[prep] buffer       : {args.buffer} Å")
    print(f"[prep] box shape    : {args.box_shape}")
    print(f"[prep] salt conc    : {args.salt_conc} M")
    print(f"[prep] output dir   : {out_dir}")
    print(f"[prep] prefix       : {prefix}")
    print()

    # 1) antechamber
    bcc_flag = "bcc" if args.charge_method == "bcc" else "gas"
    antechamber_cmd = [
        "antechamber",
        "-i", str(src),
        "-fi", fmt,
        "-o", str(mol2),
        "-fo", "mol2",
        "-c", bcc_flag,
        "-s", "2",
        "-nc", str(args.net_charge),
        "-m", str(args.multiplicity),
        "-at", "gaff2",
    ]
    _amber.run_cmd(antechamber_cmd, cwd=out_dir)

    # 2) parmchk2
    parmchk_cmd = [
        "parmchk2", "-i", str(mol2), "-f", "mol2", "-o", str(frcmod),
        "-s", "gaff2",
    ]
    _amber.run_cmd(parmchk_cmd, cwd=out_dir)

    # 3) tleap
    _amber.write_tleap_deck(
        tleap_in,
        prefix=prefix,
        mol2=mol2,
        frcmod=frcmod,
        water=args.water,
        buffer_a=args.buffer,
        neutralize=not args.no_neutralize,
        salt_conc=args.salt_conc,
        box_shape=args.box_shape,
        implicit=args.implicit,
    )
    _amber.run_cmd(
        ["tleap", "-f", tleap_in.name],
        cwd=out_dir,
        stdout_to=tleap_log,
    )

    prmtop = out_dir / f"{prefix}.prmtop"
    rst7 = out_dir / f"{prefix}.rst7"
    if not (prmtop.exists() and rst7.exists()):
        raise SystemExit(
            f"tleap reported success but {prmtop.name}/{rst7.name} are "
            f"missing. Inspect {tleap_log}."
        )

    if not args.keep_intermediates:
        for stem in ("sqm.in", "sqm.out", "sqm.pdb",
                     "ANTECHAMBER_AC.AC", "ANTECHAMBER_AC.AC0",
                     "ANTECHAMBER_BOND_TYPE.AC",
                     "ANTECHAMBER_BOND_TYPE.AC0",
                     "ANTECHAMBER_AM1BCC.AC",
                     "ANTECHAMBER_AM1BCC_PRE.AC", "ATOMTYPE.INF",
                     "leap.log"):
            f = out_dir / stem
            if f.exists():
                f.unlink()

    print()
    print(f"[prep] wrote {prmtop}")
    print(f"[prep] wrote {rst7}")
    if not args.implicit:
        print(f"[prep] wrote {out_dir / (prefix + '_solvated.pdb')}")
    print()
    print("Next: run MD via")
    print(f"  python scripts/amber_md.py --prmtop {prmtop} --rst {rst7} "
          "--stage min --output-dir <run-dir>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
