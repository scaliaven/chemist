# Add-ons (v1.0) — Framing and Extension Surface

## What "add-on" means here

Add-ons consume the MD output. They are not co-equal verbs with
`amber_md.py` / `amber_remd.py`. Run MD first; then run an add-on
on the trajectory. This framing keeps the SKILL.md routing rule
sharp: MD-deep prompts go to the MD core, after-MD prompts go to
the add-ons.

## v1.0 add-ons

| Tool | Verb | Reads | Writes |
|---|---|---|---|
| `amber_sp.py --mode snapshot` | one-shot energy on a single rst7 (`imin=5, maxcyc=0`) | `.prmtop`, `.rst7` | `<prefix>.json` (decomposed energy terms) |
| `amber_sp.py --mode trajectory` | per-frame energies via cpptraj `esander` | `.prmtop`, `.nc` | `<prefix>_energies.dat` |
| `amber_analyze.py` | RMSD/RMSF/RDF/hbond/radgyr via cpptraj | `.prmtop`, `.nc` | per-analysis CSV + PNG |
| `amber_analyze.py --demux-remd` | demux a finished REMD into per-T trajectories | `.prmtop` + `<remd-out>` | per-T `.nc` files |
| `amber_score.py` | MMPBSA/MMGBSA endpoint binding free energy | three `.prmtop`s + `.nc` | MMPBSA `.in` + `_summary.json` |

Each add-on's reference file documents its idioms:

- `single_point.md` — `imin=5` snapshot vs cpptraj `esander` trajectory
- `analysis.md` — cpptraj actions used by `amber_analyze.py`
- `scoring.md` — MMPBSA decks used by `amber_score.py`

## Extension surface — adding a new add-on

When v1.x users ask for a new add-on, follow the convention so the
next one lands predictably. Don't re-architect.

### 1. Naming

`scripts/amber_<noun>.py`. Examples slated for later:

| Hypothetical script | What it does | Trigger |
|---|---|---|
| `amber_parmed.py` | Topology mutation via ParmEd | "rename atom types"; "remove waters"; "merge prmtops" |
| `amber_mbar.py` | MBAR free energy from REMD or US | "MBAR"; "free-energy reweighting"; "WHAM" |
| `amber_cluster.py` | Conformational clustering via cpptraj `cluster` | "cluster the trajectory"; "find conformers" |
| `amber_dssp.py` | Secondary structure via cpptraj `secstruct` | "DSSP"; "secondary structure timeline" |

Or, for mdin-flag-only add-ons, **prefer extending an existing
script with a flag** rather than creating a new script. Examples:

| Feature | Lands as | Why a flag, not a script |
|---|---|---|
| Accelerated MD | `amber_md.py --boost amd ...` | Just an mdin block; same engine; same outputs |
| Steered MD | `amber_md.py --boost smd --jar-file <DISANG>` | Same |
| Umbrella sampling | `amber_md.py --boost umbrella --restraint-file <DISANG>` | Same |
| Conformational clustering | `amber_analyze.py --cluster ...` | Just another cpptraj action |
| DSSP | `amber_analyze.py --dssp` | Same |
| REMD swap-rate stats | `amber_analyze.py --remd-stats` | Reads rem.log; already partially exposed |

### 2. Inputs

Standard: `--prmtop` and either `--rst` (snapshot-flavored) or
`--trajectory` (frame-iterating). Add-ons that need more
(e.g. MMPBSA's three prmtops) declare them but follow the same
`amber_<noun>.py` shape.

### 3. Outputs

Per-add-on directory under `--output-dir`. Always write
`<prefix>_summary.json` so other tools (or the next add-on) can
chain. Plot to `<prefix>_<analysis>.png` and CSV to
`<prefix>_<analysis>.csv` to match the `analyze_traj.py` output
shape.

### 4. Helpers

Every add-on imports `_amber.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _amber

engine = _amber.pick_engine(args.engine)            # auto MPI / non-MPI
mdin_text = _amber.render_min(maxcyc=10000, ...)    # mdin templates
energies = _amber.parse_mdout(mdout)                # mdout scalars
rates = _amber.parse_remlog(rem_log)                # rem.log acceptance
ok = _amber.mdout_succeeded(mdout)                  # 'Total wall time' marker
_amber.run_cmd(cmd, dry_run=args.dry_run)           # subprocess + dry-run
```

No duplicated subprocess plumbing across scripts.

### 5. Registration

- Add a row to SKILL.md's "Add-ons" table.
- Append the trigger phrases to SKILL.md's description add-on phrase
  block (kept visually distinct from MD-core phrases).
- Add a topic-scoped reference file under `references/`.

### 6. Reference file shape

A reference file should be:

- Recipe-style (drop-in commands the model can paste).
- One topic.
- ~100-300 lines max. If it grows past that, split into sub-files
  using `<topic>_<aspect>.md` like `ase-simulation`'s reference
  refactor.

### 7. mdin-flag-only changes — prefer flags

Anything that's just "add this block to mdin" should land as a flag
on `amber_md.py`, not a new script. Compelling reasons to make a
new script:

- New file format or parser (e.g. cpptraj `clusterout` requires its
  own decoding).
- New engine binary (e.g. `MMPBSA.py`).
- New post-processing pipeline that other add-ons should be able to
  chain into.

When in doubt, prefer the flag — fewer scripts means fewer
trigger surfaces and a tighter routing contract.

## Big add-ons not yet shipped

See `extension_map.md` for the full list with where-they-would-land
notes. The point of this skill's add-on framing is exactly that —
new add-ons land in known places without architectural debate.
