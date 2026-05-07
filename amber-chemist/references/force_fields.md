# Force Fields (v1.0)

## What ships in v1.0

**GAFF2 + AM1-BCC** for small organic molecules.

- **GAFF2** — General Amber Force Field 2; covers organic molecules
  with H/C/N/O/F/Cl/Br/I/P/S. Parameterized against high-level QM
  data; the Amber-ecosystem successor to GAFF.
- **AM1-BCC** — semi-empirical AM1 charges + Bond Charge Corrections.
  Calibrated against HF/6-31G* RESP charges; ~3-5x faster than RESP
  with similar accuracy for druglike molecules. Default in
  `antechamber -c bcc -s 2`.

`amber_prep.py --force-field gaff2` (default) drives:

1. `antechamber -c bcc -s 2 -nc <q> -at gaff2` — assigns AM1-BCC
   partial charges, writes a GAFF2-typed .mol2.
2. `parmchk2 -s gaff2` — fills missing GAFF2 parameters into a
   `.frcmod` (force-field modification file).
3. `tleap` — `source leaprc.gaff2`, load the .mol2 + .frcmod,
   solvate, neutralize, save prmtop/rst7.

## Water models

| Model | When to use | Pairs well with |
|---|---|---|
| **TIP3P** (default) | GAFF2's calibration target; production-grade for organics | GAFF2 |
| **OPC** | More accurate 4-site model; calibrated against ab initio | ff19SB (proteins, v1.1) |
| **SPCE** | Slightly different liquid properties (density, dielectric) | When user explicitly asks for SPCE |
| **TIP4P-Ew** | Ewald-tuned 4-site; good for free-energy work | TI / FEP (deferred) |

`amber_prep.py --water` accepts all four.

## Charge methods

| Method | Flag | When to use |
|---|---|---|
| AM1-BCC | `--charge-method bcc` (default) | Default for druglike organics |
| Gasteiger | `--charge-method gas` | Toy-grade; debugging only |
| External RESP | `--charge-method resp_external --resp-charges-file q.dat` | v1.1+ pre-wired hook (raises today). Use when user has RESP charges from a Gaussian calculation. |

Wrong `--net-charge` is the #1 prep failure mode. AM1-BCC
silently shifts every partial charge if the formal charge doesn't
match. Always check the net charge against the SMILES /
Lewis structure before running.

## Box options

| Flag | Effect |
|---|---|
| `--box-shape rect` (default) | `solvateBox` — rectangular periodic box |
| `--box-shape oct` | `solvateOct` — truncated octahedron, ~30% fewer waters |
| `--buffer 12.0` (default) | Solvent layer thickness in Å |
| `--salt-conc 0.150` | Approximate salt concentration in M |
| `--no-neutralize` | Skip neutralizing counter-ions |
| `--implicit` | Skip solvateBox/addions entirely (vacuum / GB) |

Truncated octahedron is more efficient for roughly-spherical
solutes. Stick with rectangular if the molecule is elongated or
the user wants to do RDFs across the box.

## What's deferred to v1.1+

Pre-wired but raises `NotImplementedError` today. Architecture is
visible in `amber_prep.py`'s argparse — these flags exist, the
implementation lands later.

| Force field | Use case | Plan |
|---|---|---|
| **ff14SB** | Proteins (older, still widely cited) | v1.1 |
| **ff19SB** | Proteins (current Amber default; pairs with OPC) | v1.1 |
| **OL21** | Nucleic acids (DNA/RNA, AmberTools25) | v1.1 |
| **LIPID17** | Membrane / lipid bilayers | v1.x candidate; needs anisotropic barostat |

When the user asks for any of these, defer honestly:

> v1.0 ships GAFF2 small-molecule prep only. ff19SB+OPC for proteins
> and OL21 for nucleic acids are pre-wired (raise today). If you
> already have a prmtop from CHARMM-GUI / AmberTools' tleap on a
> PDB, pass `--from-prmtop` to `amber_run.py` / `amber_md.py` /
> `amber_remd.py` — the MD core is force-field-agnostic.

That last point is important: the MD core is just running pmemd
against whatever prmtop you give it. ff19SB-prepared prmtops will
run fine through `amber_md.py`; only the prep stage is gated.

## Why not GAFF1?

GAFF2 supersedes GAFF for almost all use cases. Stick with GAFF2
unless the user is reproducing a published GAFF1 study. There is no
GAFF1 flag in v1.0.

## Why not OpenFF?

OpenFF (the Open Force Field initiative's smirnoff99Frosst /
Sage / Parsley families) is a different ecosystem from
GAFF/Amber. v1.0 stays in the Amber lane because the rest of the
toolchain (pmemd, MMPBSA.py, cpptraj's esander) is calibrated for
Amber-style force fields. OpenFF support would need its own design
pass — not v1.0.

## Reference manual

- GAFF2 paper: Wang et al. 2004 (GAFF) + Vanommeslaeghe et al. 2010 + later revisions; documented at `https://ambermd.org/antechamber/gaff.html`.
- AM1-BCC: Jakalian et al. 2002.
- ff19SB: Tian et al. 2020.
- OL21: Galindo-Murillo et al. 2016 (OL15) + AmberTools25 docs.
- See `manual_lookup.md` for current URLs.
