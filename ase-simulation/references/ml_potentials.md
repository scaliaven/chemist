# ML Potentials Reference (STUB — planned for v2, not implemented)

> **ML potentials are not yet supported by the ase-simulation skill.**
> Do not import `mace_torch`, `chgnet`, `matgl`, `sevenn`, or
> `orb_models` in a skill response, and do not construct an ASE
> calculator from any of them. This file exists to (a) document how
> the environment detects each package, (b) record the intended v2
> scope, and (c) capture the open questions that two weeks of real-
> usage data are expected to answer.

## §1. Status

ML potentials are planned for **v2**. They are not currently supported.

The framing — and this matters — is that ML potentials are an
**accelerator on top of trusted methods, not a replacement for them.**
A good v2 chapter on ML potentials will look more like "here is how to
get a 100× speedup with cross-validation against xTB or DFT" than "here
is a black-box DFT replacement." When users ask about ML potentials
today, set that expectation explicitly:

- For organic / main-group systems, recommend **GFN2-xTB**. It is
  trusted, it has no calibration burden, and it covers most v1 use
  cases. Note honestly that it gets impractical past ~1k atoms — that
  is precisely where ML potentials are intended to land.
- For inorganic materials and bulk crystals, recommend **EMT** (for
  EMT-supported metals) or honest acknowledgment that v1 has no
  general-purpose materials calculator.
- If the user explicitly wants MACE / CHGNet / Orb today, tell them
  the skill cannot drive these yet. They can run the package directly
  outside the skill; the skill can help with **trajectory analysis**
  afterwards via `analyze_traj.py`.
- Do **not** spin up an ML potential inline in a skill response. The
  validation infrastructure (cross-checks against xTB or DFT, drift
  monitoring, OOM handling on GPU) is not in place yet, and getting
  it wrong silently produces a plausible-looking PES that is wrong in
  ways the user will not notice.

## §2. Detection

`scripts/check_env.py` should try to import each of the major ML
potential packages and report version-or-missing for each. None of
these affect the v1 capability summary; they appear only in the v2
preview block.

| Package | Import name | Foundation model(s) of interest |
|---|---|---|
| MACE | `mace_torch` | MACE-MP-0 (organics + materials) |
| CHGNet | `chgnet` | CHGNet (inorganic materials, charge-aware) |
| M3GNet | `matgl` | M3GNet via the unified matgl package |
| SevenNet | `sevenn` | SevenNet-0, SevenNet-l3i5 |
| Orb | `orb_models` | Orb-v2 (materials foundation model) |

Reporting rule: for each package, attempt the import; on success report
the package name and version, on failure report "not installed." Do
**not** attempt to download any model weights at env-check time — model
download is a runtime concern and a multi-GB network operation has no
business in a status check.

GPU availability also matters for ML potentials but is **out of scope**
for this stub's detection — `torch.cuda.is_available()` is a separate
concern that v2 will fold in when the calculator wrappers actually
need it.

## §3. Scope when implemented (v2)

When v2 work begins on ML potentials, the chapter that replaces this
stub will cover:

- **MACE-MP-0** as an ASE Calculator drop-in for inorganic crystals,
  bulk materials, and mixed systems (89-element coverage), used for
  geometry optimization and MD on systems where GFN2-xTB is too slow.
- **MACE-OFF** (the organics-trained MACE foundation model, 10
  elements: H/C/N/O/P/S/F/Cl/Br/I) as the parallel drop-in for
  pure-organic systems where it outperforms GFN2-xTB on torsions and
  conformers. **Same vendor, single install (`pip install
  mace-torch`)** — chosen over MACE-MP-0 + CHGNet because the dual-
  vendor pairing duplicates dependencies and forces awkward
  "is this organic enough for CHGNet to break?" routing logic.
  CHGNet is **deferred to v2.2** and lands when battery-cathode /
  charge-aware materials become a documented usage pattern.
- An **explicit, mandatory cross-validation contract.** Every v2 MD
  run with an ML potential validates by default: at every checkpoint
  interval (default 1 ps), recompute energy and forces on the latest
  frame through GFN2-xTB (organics) or a user-supplied reference
  (materials); write `validation.csv` with `step, MAE_E_meV,
  MAE_F_meV_per_A, max_F_dev_meV_per_A`; abort the run when
  `MAE_F > 100 meV/Å`. Users who want raw speed can opt out with
  `--no-validate`, but the default is on. This is non-negotiable —
  ML potentials produce plausible-looking PESs that are wrong in
  ways users do not notice, so the skill cannot recommend them
  honestly without an integrated check.
- Clear **size and accuracy guidance**: practical ceiling on a 40 GB
  GPU is **~1–2k atoms** with MACE medium, not the 10k figure earlier
  drafts of this stub claimed. CPU mode is ~10× slower; the size
  cliff effectively halves there. Users hitting OOM should drop to
  the small model or shrink the system, not push through.

It will explicitly **not** cover, in v2:

- **Training new ML potentials.** That is a research workflow with its
  own dataset / loss / hyperparameter ecosystem; it does not belong in
  a simulation-orchestration skill.
- **Fine-tuning foundation models** (MACE-MP-0, Orb, CHGNet) on user
  data. Same reasoning — research workflow, not skill workflow.
- **Active-learning loops** that alternate ML inference with reference
  DFT calls and retrain. These are end-to-end research projects and
  the skill should not pretend to drive them.
- **Equivariant / message-passing internals.** v2 will use these
  packages as black-box ASE calculators. Anyone who needs to peek
  inside should read the package docs directly.

These are explicitly v3+ (or "not in scope at all") candidates.

## §4. Open questions (to be answered by usage data)

1. **Which package is the dominant ask — MACE, CHGNet, Orb, or
   something else?** *Answered (2026-05-07): MACE.* The MACE-MP-0 +
   MACE-OFF pairing is the only foundation-model line with first-class
   checkpoints for **both** sides of the v1 method tree (materials and
   organics) under a single install. CHGNet → v2.2 (charge-aware
   materials), Orb-v3 → v2.2+ (confidence-head OOD signal). Other
   packages (M3GNet, SevenNet, MatterSim) stay in detection-only
   `[v2 preview]` until usage data argues for them.
2. **Molecules or materials — which audience is louder?** MACE-MP-0
   covers both but the workflows diverge (MD vs. structure search,
   PBC vs. no PBC, charges vs. no charges).
3. **What system size do users actually want ML for?** If most
   requests are 200–500 atoms (where xTB is fine), the case for ML
   weakens; if requests cluster at 5k–50k, ML is a clear win and the
   cross-validation overhead is acceptable.
4. **Is the cross-validation overhead acceptable, or do users want
   raw speed?** A snapshot every 1 ps through xTB is meaningful but
   non-trivial; users may push back. The right framing depends on
   what they're using ML for (production trajectories vs. exploratory
   sampling).
5. **GPU assumption.** When v2 lands, do most skill users have a GPU
   available? CPU MACE is usable but ~10× slower; if most users are
   CPU-only the size-cliff calculus changes.
