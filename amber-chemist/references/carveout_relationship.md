# Relationship with `ase-chemist`'s v1.3 Amber Carve-Out

## The two skills

`ase-chemist` v1.3 ships a small Amber carve-out:
`scripts/parameterize_gaff2.py` + `scripts/run_amber.py`. It does
**exactly one thing**: GAFF2-only small-molecule plain `min → heat
→ density → prod` NPT MD via shell-out to pmemd. It is a focused
slice — there is no REMD, no implicit-solvent, no cpptraj-driven
analysis, no MMPBSA, no biomolecular force fields, no
extend-an-existing-prod, no Monte Carlo barostat. The carve-out
exists because `ase-chemist`'s primary lane (ASE-driven
in-process Calculators) doesn't have a graceful way to drive pmemd
at production speeds.

`amber-chemist` v1.0 is the **deeper Amber-native sibling**. It
ships the full MD core (configurable stages, restart, extend,
restraints, Berendsen / Monte Carlo / no barostat, explicit or
implicit solvent), T-REMD as a v1.0 first-class capability,
cpptraj-driven analysis (RMSD/RMSF/RDF/hbond/radgyr + REMD demux),
single-point energies, and MMPBSA endpoint scoring. ff19SB / OL21
biopolymer prep is pre-wired and lands in v1.1.

The two skills coexist. `ase-chemist/SKILL.md`'s description and
the v1.3 carve-out scripts are **not modified** by `amber-chemist`.

## Routing — which skill answers which prompt

The trigger-phrase split puts each prompt in exactly one of three
buckets.

### `amber-chemist` wins (Amber-deep vocabulary)
- REMD / replica exchange / parallel tempering / temperature ladder
- MMPBSA / MMGBSA / endpoint binding free energy / alanine scan / per-residue decomposition
- cpptraj / esander / per-frame energy decomposition
- Implicit solvent / GB / GBneck2 / igb=N / OBC
- Extend a prod / restart from rst7
- ff19SB / ff14SB / OL21 / OPC water as a force field

### `ase-chemist` wins (ASE-shaped vocabulary)
- HOMO-LUMO / xTB / GFN2 / GFN1
- MACE / MACE-OFF / MACE-MP / foundation model
- EMT / Lennard-Jones / TIP3P with FixBondLengths
- Gaussian / B3LYP / DFT / def2-TZVP
- Slab building / Pt(111) / fcc111 / surface
- ase.build / ase.vibrations / NEB inline

### Either skill is OK (shared zone)
- "GAFF2 + AM1-BCC + TIP3P production MD" with no other Amber-deep
  terms. Both descriptions enumerate the relevant phrases; both
  produce a correct script. The user picks based on which other
  features they want to chain (e.g., need MMPBSA after? Use
  `amber-chemist`. Need to also do an xTB single-point comparison?
  Use `ase-chemist`).

## Why two skills, not one

Three reasons:

1. **Routing clarity.** Tools that span multiple ecosystems (ASE +
   Amber + Gaussian + MACE) tend to grow descriptions that overload
   trigger phrases and degrade routing reliability. Splitting by
   ecosystem (ASE-orchestrated vs Amber-native) keeps each
   description focused.
2. **Architectural honesty.** The Amber carve-out is documented in
   `ase-chemist`'s PLAN.md as a "we declined to make this go
   through ASE because pmemd.cuda is too valuable to lose." That's
   a real architectural choice, not a defect. `amber-chemist` exists
   precisely so the Amber side can grow features (REMD, MMPBSA) that
   don't fit the ASE-orchestrator framing without weighing down
   `ase-chemist`'s focus.
3. **Independent evolution.** `amber-chemist` v1.1 ships ff19SB+OPC
   protein MD; `ase-chemist` v2.x might pursue MACE-driven
   biomolecular MD. Both are "biomolecular MD" but use entirely
   different toolchains; couplings would be artificial.

## What this means for the user

When in doubt:

- "I want to run Amber" → `amber-chemist`.
- "I want to run quantum-chemistry-flavored simulation" → `ase-chemist`.
- "I want both, chained" → run them sequentially; the file outputs
  (prmtop, rst7, .nc trajectory) are interchangeable.

The shared GAFF2 zone is intentional — it's the most common Amber
prompt, and routing it to either skill produces a correct answer.

## Reading order if you're new to both

1. `ase-chemist/README.md` — understand the orchestrator framing.
2. `ase-chemist/references/amber.md` — understand the v1.3 carve-out's scope and the four-options-deferred decision.
3. `amber-chemist/README.md` — understand the MD-first scope.
4. `amber-chemist/references/extension_map.md` — understand which Amber features are not yet shipped and where they would land.
5. The `ase-chemist` PLAN.md §Phase 3 documented four options for the carve-out's resolution. With `amber-chemist` shipping, there is now a fifth: keep the carve-out as-is, ship `amber-chemist` as the deeper sibling, and let users pick by trigger phrase. v1.0 of `amber-chemist` took option 5.
