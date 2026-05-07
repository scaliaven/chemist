# Gaussian Reference (STUB — planned for v2, not implemented)

> **This backend is not yet supported by the ase-simulation skill.** Do
> not generate Gaussian input files (`.gjf` / `.com`) or shell out to
> `g16` / `g09` from within a skill response. This file exists to (a)
> document how the environment detects a Gaussian install, (b) record
> the intended v2 scope, and (c) capture the open questions that two
> weeks of real-usage data are expected to answer.

## §1. Status

Gaussian is planned for **v2**. It is not currently supported. If the
user asks for a task that needs Gaussian, do this today:

- For energies, geometry optimization, and frequency analysis on small
  organic / main-group systems, recommend **GFN2-xTB**. Be honest that
  the accuracy is semi-empirical, not DFT — quote ~few-kcal/mol error
  bars on relative energies, larger on barriers.
- If the user explicitly needs DFT-level numbers (publication-quality
  thermochemistry, reaction barriers within ~1 kcal/mol, transition-
  metal catalysis where xTB fails), tell them honestly that the skill
  cannot drive Gaussian yet. Users with a Gaussian license should run
  it manually outside the skill; afterwards, the skill can help parse
  output (cclib reads Gaussian `.log` files) and analyze any geometries
  or trajectories produced.
- Do **not** hand-write a `.gjf` deck and shell out from a skill
  response. That code path is not tested and silently producing wrong
  route lines (basis sets, route keywords, multiplicities) is exactly
  the failure mode v2 needs to prevent.

## §2. Detection

`scripts/check_env.py` should report Gaussian as available iff a
production binary is on `PATH`:

| Check | Purpose |
|---|---|
| `shutil.which("g16")` | Gaussian 16 — preferred if both are present |
| `shutil.which("g09")` | Gaussian 09 — older, still common at some sites |
| `os.environ.get("GAUSS_EXEDIR")` | exec dir; signals a properly-sourced env |
| `os.environ.get("GAUSS_SCRDIR")` | scratch dir; large I/O target, must be set |

Reporting rule: the backend is "available" if **either** `g16` or `g09`
resolves on `PATH`. Report which version was found and the resolved
path. If `GAUSS_EXEDIR` is unset even when the binary resolves, flag
that — running Gaussian without a sourced environment is a common silent
failure.

Do **not** check whether the **license server** is reachable. Gaussian
licenses are FlexLM-style and probing is fragile (multi-second hangs,
firewall variation by site). Note in the stub-reference output that a
license is required and let the user discover license issues at run
time.

## §3. Scope when implemented (v2)

When v2 work begins on Gaussian, the chapter that replaces this stub
will cover:

- **Single-point energies** at a user-specified method/basis, with cclib
  parsing of energies, (when present) dipoles, Mulliken / Löwdin /
  Hirshfeld charges, and orbital energies. **NPA charges are out of
  scope for v2** — cclib's main attribute set does not expose NPA, and
  the cclib NBO parser is a separate dependency / parser path. NPA
  support is a v3 candidate.
- **Geometry optimization** via `GaussianOptimizer` (which delegates to
  Gaussian's own L103 optimizer — much faster than wrapping ASE
  optimizers around Gaussian single points), plus a tight-criteria
  mode for vibrational input.
- **Frequency analysis** (`Freq`), including thermochemistry parsing
  (ZPE, enthalpy, Gibbs free energy) at the requested temperature.
  Implementation note: `ase.io.gaussian.read_gaussian_out` does **not**
  parse vibrational frequencies — the Freq workflow must use cclib for
  output parsing, not the ASE reader.
- **Transition-state searches** via `Opt=TS` plus QST2/QST3 starting
  points; an explicit warning that these need good guesses. *(This
  may move to v3 — TS searches need a good Hessian guess (`CalcFC`/
  `ReadFC`) and post-hoc IRC verification, neither of which fits the
  "skill writes a script, user runs it" pattern.)*
- **Implicit solvation** via `SCRF=(SMD,Solvent=...)` as the default for
  aqueous and polar-solvent work (SMD beats IEF-PCM by ~3–5 kcal/mol
  RMSD on solvation free energies). PCM stays available as an opt-in
  for matching older literature.

It will explicitly **not** cover, in v2:

- IRC scans (`IRC=...`) — needs reaction-path post-processing.
- Anharmonic frequencies (`Freq=Anharmonic`) — expensive and requires
  careful normal-mode follow-up.
- NBO analysis (`Pop=NBO`) — output parsing is non-trivial.
- Post-Hartree-Fock correlated methods (CCSD, CCSD(T), MP2, CASSCF) —
  basis-set / memory / diskspace heuristics are method-specific.
- Excited-state methods (TDDFT, CIS, EOM-CCSD).

Those are v3+ candidates.

## §4. Open questions (to be answered by usage data)

1. **Method/basis defaults — does the skill pick, or always require the
   user to specify?** A B3LYP/6-31G(d) default is a sensible publication
   minimum but a terrible choice for transition metals; a "no defaults,
   always ask" policy is safer but reads as the skill not actually
   helping. The right answer depends on what users are actually
   computing.
2. **Solvation defaults.** *Answered (2026-05-07): default to SMD when
   the user says "in water" or names a solvent.* SMD outperforms
   IEF-PCM by ~3–5 kcal/mol RMSD on aqueous solvation free energies
   (SAMPL benchmarks); PCM stays available as an opt-in flag for users
   matching older literature.
3. **Output parsing — cclib or roll our own?** *Answered (2026-05-07):
   cclib.* ASE's own `read_gaussian_out` deliberately does not parse
   frequencies, so a Freq workflow must use cclib regardless. Adding
   the cclib dependency is cheaper than maintaining a regex parser
   for thermochem blocks that change route-line-by-route-line.
4. **Resource defaults — `%mem` and `%nprocshared`.** These belong in
   the input deck and depend on the host. How does the skill know
   what's safe? Probe `psutil` at script time, or always require the
   user to supply them?
5. **Local execution vs queue submission.** Most Gaussian jobs at HPC
   sites run via SLURM, not interactively. v2 needs to decide whether
   to run locally only (small jobs, fast turnaround) or learn to write
   submission scripts (matches reality but adds a maintenance burden).
