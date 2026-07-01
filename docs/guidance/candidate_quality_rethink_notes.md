# Candidate Quality Rethink Notes

Current candidate pool best median is about `0.65`, which is not enough to support high-quality final localization.

The max around `0.872` shows some feasible cases exist, but high-quality candidates are not stable. Top20 approaching pool ceiling shows current ranking preserves some potential, but if the pool ceiling is low, selector work cannot solve the root cause.

Candidate generation must check:

- whether candidates are centered around a wrong prior
- whether candidate diversity is real
- whether `factor_topk` is mostly duplicates
- whether structural candidates bring genuinely new positions
- whether ray peaks are clutter
- whether wedge evidence is only a local bright spot
- whether signed evidence has enough temporal support
- whether candidate box `w/h/heading` fits SAR vehicle appearance or only storage-axis convention

The next useful work is to explain candidate quality visually and structurally, not to rank the same low-ceiling pool harder.
