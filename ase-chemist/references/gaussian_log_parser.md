# Gaussian output parsing — the in-house helper

Part of the v1.4 Gaussian reference set. Companion files:
[`gaussian_method_selection.md`](gaussian_method_selection.md),
[`gaussian_no_defaults.md`](gaussian_no_defaults.md),
[`gaussian_g16_vs_g09.md`](gaussian_g16_vs_g09.md),
[`gaussian_failure_modes.md`](gaussian_failure_modes.md). Index:
[`gaussian.md`](gaussian.md).

## Output parsing — the in-house helper

`gaussian_sp.py` and `gaussian_opt.py` use ASE alone for E/F/dipole
(`ase.io.gaussian.read_gaussian_out` is fine for those). For the
fields ASE doesn't parse, v1.4 ships a small in-house helper:

- `scripts/_gaussian_log.py` — ~100 lines of regex against Gaussian's
  stable .log format. Three public functions:

  - `parse_thermochem(log_path)` — vibrational frequencies (cm⁻¹,
    signed; negative values are imaginary modes), ZPE, enthalpy,
    Gibbs free energy, thermochem temperature. Returns a dict;
    keys absent if the corresponding line wasn't in the log.
  - `parse_mulliken_charges(log_path)` — list of per-atom Mulliken
    charges from the most recent `Mulliken charges:` block (Gaussian
    prints these by default), or None if not found.
  - `parse_homo_lumo(log_path)` — `(HOMO_eV, LUMO_eV)` from the
    `Alpha occ./virt. eigenvalues` lines, or None. Gaussian
    truncates default eigenvalue output for some methods; pass
    `Pop=Reg` via `--extra-route` to force the full list.

Why in-house instead of cclib:

- **Architectural coherence.** The skill maintains an "everything
  through ASE-or-our-own-code" framing. cclib is a third-party
  output parser that wraps the same engines ASE already does;
  layering it on top adds another vendor surface to track.
- **Smaller install footprint.** `pip install cclib` pulls in
  numpy + scipy + a wide compatibility matrix. The in-house helper
  is stdlib-only (regex + pathlib).
- **Maintenance burden is small.** Gaussian's Freq output format has
  been stable across 09 → 16; the parser file is short enough to
  patch in place if a future release breaks it.

What's intentionally **not** parsed:

- **NPA charges.** Require Gaussian's `Pop=NPA` (which calls NBO);
  NBO has a different output format that's not worth a parser for
  v1.4. Recommend running NBO manually if a user asks. v3 candidate.
- **Löwdin / Hirshfeld charges.** Same reasoning — Mulliken is
  default Gaussian output; the others require explicit `Pop=`
  flags and have less consistent output blocks. Add only if usage
  data demands them.
- **Higher-derivative properties** (polarizabilities, hyperpolar-
  izabilities, IR/Raman intensities). Out of scope for v1.4.
