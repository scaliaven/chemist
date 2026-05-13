---
name: amber-chemist
description: Use this skill whenever the user wants to run, set up, restart, extend, or replicate Amber-native molecular dynamics — single-replica or replica-exchange — on small organics in explicit or implicit solvent. After the MD finishes, this skill also drives cpptraj-based analysis (RMSD/RMSF/RDF/hbond/radgyr, per-frame energy decomposition via esander) and MMPBSA-style endpoint scoring (MMPBSA / MMGBSA, alanine scan, per-residue decomposition) as add-ons that consume the MD output. MD-core trigger phrases — "Amber MD", "production NPT in pmemd", "1 ns of explicit-solvent MD", "Berendsen barostat", "Monte Carlo barostat", "Langevin thermostat at gamma_ln", "extend my prod by 5 ns", "restart from this rst7", "implicit-solvent MD", "GB implicit", "GBneck2", "igb=2", "OBC", "min → heat → density → prod", "production pmemd run", "pmemd.cuda", "antechamber", "parmchk2", "tleap", "AmberTools", "AmberTools25", "GAFF2", "AM1-BCC", "explicit-solvent ligand binding", "TIP3P+GAFF2 production". REMD trigger phrases — "T-REMD", "temperature REMD", "replica exchange", "parallel tempering", "exchange every", "temperature ladder", "geometric replica ladder", "exchange acceptance rate", "pmemd.cuda.MPI -rem 1", "demux REMD". Add-on trigger phrases (after-MD framing) — "MMPBSA", "MMGBSA", "endpoint binding free energy", "GB binding free energy", "PB binding free energy", "alanine scan", "per-residue decomposition", "score this trajectory", "cpptraj", "esander", "RMSD via cpptraj", "RMSF via cpptraj", "hbond analysis", "radgyr", "RDF of solvent around ligand", "per-frame energy decomposition". Routing — Amber-deep prompts (REMD, MMPBSA, cpptraj, ff19SB, OL21, esander, GB-implicit MD, alanine scan) reach this skill; ASE-shaped prompts (HOMO-LUMO, xTB, MACE, EMT, Gaussian DFT, slab building, Pt(111)) reach the sibling `ase-chemist` skill. The shared zone — GAFF2 + AM1-BCC + TIP3P + plain MD — is genuinely shared and either skill produces a correct answer.
license: MIT
---

# amber-chemist Skill (v1.0)

This skill is the Amber-native sibling to `ase-chemist`. It is
**MD-first**: the v1.0 verb is normal (single-replica) MD with
configurable stages, restart-and-extend, restraints, barostat
options, explicit or implicit solvent, and a verbatim-mdin escape
hatch. **T-REMD** is built on top of that core and ships in v1.0
too — currently the strongest differentiator vs `ase-chemist`'s
narrower v1.3 carve-out (which cannot do REMD). Analysis (cpptraj)
and endpoint scoring (MMPBSA) are add-ons that consume the MD
output, not co-equal verbs.

## Always do this first

```bash
python scripts/check_env.py
```

The output ends with a `[SUMMARY]` line that names exactly which
workflows your environment supports right now.

**Environment-driven fallback strategy:**
1. Parse the `[SUMMARY]` to determine available engines (pmemd.cuda, pmemd.cuda.MPI, pmemd, sander, etc.).
2. If the user requests REMD but only single-replica engines are available, always recommend single-replica MD as the fallback.
3. If the user requests implicit-solvent MD but only explicit-solvent libraries are present, report the gap clearly.
4. Recommend the strongest path that the environment can run today; do not fabricate workarounds.

## MD-core method selection

| Task | Tool | Notes |
|---|---|---|
| One-shot pipeline (prep + min + heat + density + prod) | `scripts/amber_run.py` | Default mode `standard`. `--time 1ns` style. Use `--from-prmtop` to skip prep when the user has a CHARMM-GUI prmtop. |
| One-shot REMD pipeline | `scripts/amber_run.py --mode remd` | Chains prep + min + heat + density + REMD-prod. `--n-replicas`, `--t-low`, `--t-high`, `--exchange-every`. **Requires `.MPI` engine.** |
| One-shot implicit-solvent MD | `scripts/amber_run.py --mode implicit` | Skips solvateBox; skips density (no PBC). `--implicit-gb gb2`. |
| GAFF2 prep alone (small organic) | `scripts/amber_prep.py` | antechamber AM1-BCC → parmchk2 → tleap. `--water`, `--buffer`, `--box-shape oct`, `--salt-conc`. |
| Stage-level MD control | `scripts/amber_md.py --stage {min,heat,density,prod,custom}` | Per-stage flags: `--restraint-mask`, `--barostat monte_carlo`, `--implicit-solvent gb2`, `--mdin <file>` (escape hatch). |
| Restart from a previous stage | `scripts/amber_md.py --restart` | `irest=1, ntx=5`. Used for chaining heat→density→prod. |
| Extend an existing prod by N more ps | `scripts/amber_md.py --extend` | Auto-numbers `prod_2.{nc,rst7,mdout}`, `_3`, etc. Works on the same stage. |
| T-REMD (multi-replica enhanced sampling) | `scripts/amber_remd.py` | Auto temperature ladder, groupfile, exchange-rate report parsed from `rem.log`. **Requires `.MPI` engine.** |

*Deep dive: `references/md_core.md` for stage rendering, restart vs extend, restraints, barostat options, and implicit-solvent (GB) MD.*

## Add-ons (consume MD output; not part of the MD core)

*Framing: `references/add_ons.md` explains why add-ons consume MD output rather than acting as co-equal verbs, plus the extension-surface convention.*

| Add-on | Tool | Notes |
|---|---|---|
| Single-point energy on a snapshot | `scripts/amber_sp.py --mode snapshot` | `imin=5, maxcyc=0` via pmemd; returns decomposed energy. See `references/single_point.md` for the snapshot-vs-trajectory trade-off. |
| Per-frame energy decomposition over a trajectory | `scripts/amber_sp.py --mode trajectory` | cpptraj `esander` action; returns per-frame totals + components. See `references/single_point.md`. |
| RMSD / RMSF / RDF / hbond / radgyr | `scripts/amber_analyze.py` | cpptraj-driven; CSV + PNG per analysis. `--demux-remd --remd-dir <dir>` to demux a finished REMD into per-temperature trajectories. |
| Endpoint binding free energy (MMPBSA / MMGBSA) | `scripts/amber_score.py` | `--method gb|pb|both`, `--per-residue`, `--alanine-scan`, `--mpi N`. |

## Force-field selection (v1.0)

Today: **GAFF2 + AM1-BCC** for small organics in TIP3P / OPC / SPCE /
TIP4P-Ew water (or vacuum / implicit GB). That's the only path
`amber_prep.py` runs.

`--force-field {ff14SB, ff19SB, OL21}` is **pre-wired** but raises
`NotImplementedError` in v1.0. Biopolymer prep (proteins, nucleic
acids, complexes) lands in v1.1. When the user asks for protein MD,
say so honestly: this skill ships GAFF2-only today; ff19SB+OPC and
OL21 are deferred. See `references/extension_map.md` for where each
deferred feature would land.

*Deep dive: `references/force_fields.md` for GAFF2/AM1-BCC details, supported water models (TIP3P / OPC / SPCE / TIP4P-Ew), and the deferred biopolymer set (ff19SB, OL21, LIPID17).*

## Engine selection

| Workload | Auto-pick order | Override |
|---|---|---|
| Plain MD (`amber_md.py`) | `pmemd.cuda > pmemd > sander` | `--engine` |
| REMD (`amber_remd.py`) | `pmemd.cuda.MPI > pmemd.MPI > sander.MPI` | `--engine` (must be `.MPI`) |

Auto-fail with a clear message if no engine of the right flavor is
on PATH. AmberTools25 is fully open-source, including pmemd.cuda; if
the user is on a fresh install and missing pmemd.cuda, point them at
`https://ambermd.org/GetAmber.php`.

## Verification & clarification

### Don't ask what's already named — and frame what you do ask

The two failure modes to avoid: silently picking wrong physics (a
wrong `--net-charge` shifts every AM1-BCC partial charge; a REMD
ladder with 50 K gaps lands far below the 15-50% acceptance window;
MMPBSA on an implicit-only prmtop is wrong physics), and re-asking
the user something the prompt or input file already names.

When the answer is genuinely underdetermined, frame the question with
the option you'd pick and the reason — e.g., *"8 replicas geometric
300-400 K gives ~12 K gaps, which should land inside the 15-50%
acceptance window; keep that or hand-tune?"* — beats a blank "what
ladder?".

### Ask the user to verify before recommending execution

After choosing parameters, restate them in a short block and ask the
user to confirm before suggesting they run anything. What to surface
depends on the verb:

**Single-replica MD (`amber_run.py --mode standard` / `amber_md.py`):**

- Force field + water model (GAFF2 + TIP3P, etc.)
- Net charge (silent-shift failure mode if wrong)
- Engine (pmemd.cuda / pmemd / sander)
- Buffer / box shape, salt conc if non-zero
- Stage durations (heat ps, density ps, prod ns) and barostat
- Restraints (mask + weight) if any
- Output directory

**T-REMD (`amber_remd.py` / `amber_run.py --mode remd`):**

- N replicas + T-low / T-high + ladder shape
- Exchange-every (steps) and total time per replica
- MPI engine + launcher (`mpirun` vs `srun`)
- Implicit-solvent flag if relevant
- Expected acceptance window — flag if any pair-gap exceeds ~15 K
  or if N replicas is below 4

**Add-ons (`amber_score.py`, `amber_analyze.py`, `amber_sp.py`):**

- MMPBSA: method (gb / pb / both), igb model, ionic strength, frame
  range, MPI count
- Analyze: which analyses (rmsd / rmsf / rdf / hbond / radgyr),
  masks, reference frame
- SP: mode (snapshot / trajectory), implicit-solvent flag if the
  prmtop is GB

Keep it tight — a 4-6 line summary, not a paragraph. If the user has
already approved the plan, don't re-ask.

## Carve-out relationship with `ase-chemist`

`ase-chemist` ships a v1.3 small-molecule Amber carve-out
(`parameterize_gaff2.py` + `run_amber.py`) that does plain GAFF2
NPT MD only. `amber-chemist` is the **deeper Amber-native sibling**:
restart-and-extend, REMD, implicit solvent, cpptraj-driven analysis,
MMPBSA scoring. The two skills coexist; routing falls out of the
trigger-phrase split (Amber-deep phrases reach here; ASE-shaped
phrases reach `ase-chemist`).

If the user is on a prompt in the shared zone (GAFF2 + AM1-BCC +
TIP3P + plain MD, no Amber-deep terms), either skill produces a
correct answer. See `references/carveout_relationship.md` for the
two-paragraph version.

## Looking up Amber semantics

The Amber Reference Manual is the canonical source for mdin keyword
behavior, force-field options, and file formats. Common references
bundled here:

- `references/manual_lookup.md` — curated URLs (Amber Reference Manual, AmberHub, tutorials, cpptraj/MMPBSA PDFs).
- `references/mdin_keywords.md` — the ~50 most-asked mdin keywords as a flat table with manual section pointers.
- `references/cpptraj_idioms.md` — recipe-style cpptraj commands (rms, atomicfluct, rdf, hbond, radgyr, esander, ensemble, strip, autoimage).
- `references/mmpbsa_idioms.md` — drop-in MMPBSA decks (GB-only, PB+GB, alanine, per-residue, MPI).

When a user asks "what does `<keyword>` do?", check
`mdin_keywords.md` first, fall back to `manual_lookup.md` for the
Reference Manual section.

**Smell test — don't fabricate.** If you are about to write *"I
think `<keyword>` defaults to ..."* or *"the standard value for
`<flag>` is roughly ..."*, stop and check the manual first.
Hallucinated Amber semantics is a high-cost, hard-to-detect failure
mode — pmemd often *runs* with the wrong value and produces
plausible-looking output that misleads downstream analysis.

## Add-on extension surface

When a new add-on is requested, follow the convention so the next
add-on lands predictably:

1. **Naming**: `scripts/amber_<noun>.py`.
2. **Inputs**: `--prmtop` and either `--rst` or `--trajectory`.
3. **Outputs**: per-add-on directory under `--output-dir`, with `<prefix>_summary.json` for chaining.
4. **Helpers**: import `_amber` for engine pick, mdin / cpptraj-deck rendering, mdout / rem.log / MMPBSA.dat parsing.
5. **Registration**: add a row to the "Add-ons" table above and a topic-scoped reference file under `references/`.
6. **mdin-flag-only changes**: prefer extending an existing script with a flag (e.g. `amber_md.py --boost amd`) over creating a new script.

`references/extension_map.md` lists the big Amber features not yet
shipped and which script each one would land in (aMD, SMD, umbrella
sampling, MBAR, H-REMD, TI/FEP, constant-pH, QM/MM, membrane,
PLUMED).

## Reporting results

When you finish a task, report:

1. The pipeline used (prep + stages, or REMD config, or scoring deck)
   and **why** it was chosen given system size, available engines,
   and what the user asked for.
2. Final numbers with units: trajectory length (ns), final temperature
   / density / volume parsed from the last mdout, REMD per-pair
   exchange acceptance rates (flag any outside [15%, 50%]), MMPBSA
   `delta_total ± std-err` if scoring.
3. Where outputs were written: prmtop / rst7 / `.nc` trajectory /
   mdout / `exchange_rate.txt` / `<prefix>_summary.json`.
4. Any caveats — e.g., "Berendsen for density only; prod ran with
   Monte Carlo", "REMD acceptance was 18% on the highest pair —
   borderline; consider one more replica", "MMPBSA GB-only — PB is
   ~2× slower but more defensible for publication".

## Honest deferrals

When the user asks for something this skill does not ship, point at
`references/extension_map.md` rather than fabricating a workflow. For
things this skill DOES ship but where the user is hitting trouble,
check `references/failure_modes.md` first — it catalogs known failure
modes across prep / MD / REMD / analysis / scoring with recovery
recipes. Specifically deferred in v1.0:

- **Free energy** (TI / FEP / MBAR) — `amber_fep.py` / `amber_mbar.py` would land here.
- **Enhanced sampling other than T-REMD** — aMD, SMD, umbrella, metadynamics — mostly mdin-flag changes; `amber_md.py --boost {amd,smd,umbrella}` is the planned shape.
- **Hamiltonian REMD** — `amber_remd.py --type H` is pre-wired, raises today.
- **Biopolymers** (proteins, nucleic acids, complexes) — `amber_prep.py --force-field {ff19SB, OL21}` raises today.
- **Constant-pH / constant-redox MD** — `amber_cpH.py` / `amber_cpE.py` would land here.
- **QM/MM** — `amber_qmmm.py` would land here.
- **Membrane / lipid (LIPID17)** — `amber_prep.py --membrane` + `amber_md.py --barostat anisotropic`.
- **Multi-GPU pmemd.cuda** — `_amber.pick_engine(--gpu-count)` parameterization.
- **PLUMED bridge** — `amber_md.py --plumed <plumed.dat>`.

The skill must give an honest deferral pointer when asked, not pretend
to support these.
