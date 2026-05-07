# Gaussian g16 vs g09

Part of the v1.4 Gaussian reference set. Companion files:
[`gaussian_method_selection.md`](gaussian_method_selection.md),
[`gaussian_no_defaults.md`](gaussian_no_defaults.md),
[`gaussian_log_parser.md`](gaussian_log_parser.md),
[`gaussian_failure_modes.md`](gaussian_failure_modes.md). Index:
[`gaussian.md`](gaussian.md).

## g16 vs g09

v1.4 detects both at script start:

- `g16` on PATH → preferred (current generation).
- `g09` on PATH → used as fallback (still common at older sites).
- Neither → script aborts with an install pointer.

Override with `--gaussian-binary {g16,g09}`. Practical differences:

- **g16 default `SCF=Tight`** — single-points are tight by default;
  most g09 tutorials' explicit `SCF=Tight` is now redundant. Don't
  auto-add it on g16.
- **Some functionals renamed** between versions; if the user copies a
  g09 route line into a g16-driven script (or vice versa), Gaussian
  errors out with a clear "unknown method" message rather than
  silently miscomputing.
- The in-house `_gaussian_log.py` parser handles both g16 and g09
  output for the v1.4 fields (vib_freqs, thermochem, Mulliken charges,
  MO eigenvalues). The format is stable across versions; if a future
  Gaussian release breaks parsing, the helper file is small enough to
  patch in place.
