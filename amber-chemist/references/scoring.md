# Scoring Reference (MMPBSA / MMGBSA)

`amber_score.py` wraps `MMPBSA.py` (Amber's endpoint binding-free-
energy script). It is an **add-on** that consumes a finished MD
trajectory.

## What MMPBSA is

MMPBSA computes:

```
ΔG_bind ≈ <E_complex> - <E_receptor> - <E_ligand>
                                + <ΔG_solv> - T·ΔS_conf
```

over a trajectory of the complex, with the receptor and ligand
extracted per-frame. The two implicit-solvent flavors:

- **MMGBSA** (`--method gb`) — Generalized Born for the polar
  solvation term. Faster (~5x), often correlates with experiment
  comparably to MMPBSA.
- **MMPBSA** (`--method pb`) — Poisson-Boltzmann for the polar
  solvation term. Slower, more rigorous on highly-charged systems.

`--method both` runs both and reports both numbers.

## What MMPBSA is NOT

- **Not** a rigorous free-energy method. Endpoint scoring drops the
  T·ΔS term (or estimates it crudely from quasi-harmonic
  analysis), and the implicit-solvent dielectric model is fixed.
  Expect ±2-5 kcal/mol absolute error; relative ranking across a
  congeneric series is more reliable.
- **Not** a substitute for TI / FEP when the user wants quantitative
  free energies. TI / FEP is on the v1.x deferred list (see
  `extension_map.md`).
- **Not** appropriate for ligands with formal charge that flips
  between protonation states — needs constant-pH MD (deferred).

When users say "compute the binding affinity," they usually mean
MMPBSA — but check whether they need rigorous numbers or a fast
ranking score.

## Inputs

```bash
python amber_score.py \
    --complex-prmtop com.prmtop \
    --receptor-prmtop rec.prmtop \
    --ligand-prmtop lig.prmtop \
    --trajectory prod.nc \
    --method gb --gb-model 2 --mpi 4 \
    --output-dir mmpbsa/
```

The three prmtops must be **gas-phase** (no waters, no ions). MMPBSA.py
strips waters and ions per-frame from `--trajectory` to extract
receptor and ligand snapshots, then evaluates each in implicit
solvent.

If your `.nc` is from an explicit-solvent run, also pass
`--solvated-prmtop sys.prmtop` so MMPBSA.py knows how to strip waters.

## GB models

| `--gb-model` | Name | When |
|---|---|---|
| 1 | Hawkins-Cramer-Truhlar | Original GB; legacy only |
| 2 | OBC (Onufriev-Bashford-Case) | Default; well-balanced |
| 5 | OBC2 | Newer OBC variant |
| 7 | GBn | Surface-area corrected |
| 8 | GBneck2 | Most modern; recommended for MMPBSA |

`--gb-model 2` is the default. `--gb-model 8` is the most modern
choice for production MMGBSA.

## Decks (rendered into `<prefix>.in`)

### GB-only
```
&general
  startframe=1, endframe=0, interval=1, keep_files=0,
/
&gb
  igb=2, saltcon=0.150,
/
```

### PB-only (mbondi2 radii)
```
&general
  startframe=1, endframe=0, interval=1, keep_files=0,
/
&pb
  istrng=0.150, radiopt=0, inp=1,
/
```

### GB + PB
Both `&gb` and `&pb` blocks present.

### Per-residue decomposition (`--per-residue`)
Add `&decomp` block:
```
&decomp
  idecomp=2, dec_verbose=1,
/
```
`idecomp=2` is per-residue, considering interactions between
different residues. `idecomp=1` is per-residue, intra-only. `=3/=4`
add backbone/sidechain breakdowns.

### Computational alanine scan (`--alanine-scan`)
Add `&alanine_scanning` block (no parameters needed):
```
&alanine_scanning
/
```
MMPBSA.py mutates each interface residue to alanine in silico and
re-evaluates the binding energy; the difference is the "ΔΔG of
alanine substitution." Useful for hot-spot identification.

## MPI parallelism

`--mpi N` switches to `MMPBSA.py.MPI` and runs through `mpirun -np N`.
Frames are distributed across ranks. Speedup is ~linear up to
~8 ranks for a typical 1000-frame trajectory.

If `MMPBSA.py.MPI` is not on PATH, the script hard-fails with a
message. Check `python check_env.py` to confirm before running.

## Output

```
mmpbsa/
  <prefix>.in                    # MMPBSA input deck
  FINAL_RESULTS_MMPBSA.dat       # MMPBSA.py's primary output
  <prefix>_summary.json          # parsed delta-G summary
  ... (other MMPBSA.py outputs if --keep-files)
```

`<prefix>_summary.json` parses the `DELTA TOTAL` line out of
`FINAL_RESULTS_MMPBSA.dat` for easy machine consumption:

```json
{
  "method": "gb",
  "gb_model": 2,
  "ionic_strength": 0.150,
  "alanine_scan": false,
  "per_residue": false,
  "n_frames_stride": 1,
  "delta_total_kcal_per_mol": -34.2,
  "std_dev": 4.1,
  "std_err_mean": 0.4
}
```

## Common failure modes

- **"Topology mismatch between -cp and -y"** — usually the trajectory
  is from a different system. Confirm the trajectory was produced from
  the complex prmtop.
- **"No frames after striping"** — `--solvated-prmtop` not set when
  trajectory has waters; MMPBSA.py can't tell what to strip.
- **MPI hangs** — usually `MMPBSA.py.MPI` ≠ pmemd MPI flavor mismatch.
  Source the same Amber environment that built the MPI variant.
- **alanine_scan finds no residues** — interface residues need to be
  in both the receptor and ligand selection; check the prmtops.

## Reference manual

- MMPBSA.py guide: `$AMBERHOME/doc/MMPBSA.pdf`. Linked from `manual_lookup.md`.
- Genheden & Ryde 2015 review of MMPBSA accuracy.
- See `mmpbsa_idioms.md` for drop-in deck recipes.
