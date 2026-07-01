# Development Protocol

## Per-Round Protocol

1. Read `docs/guidance/README.md` and the linked guidance files.
2. Write the working hypothesis for the round before writing scripts.
3. Identify input sources and whether they are runtime, audit, posthoc, or historical archive.
4. Produce visual outputs, `summary.json`, report markdown, and missing-field/path reporting for any diagnostic run.
5. Record changed files and a boundary check in the final report.

## Required Discipline

- Do not use silent fallback. If a path, field, factor, or image is missing, report it.
- Do not turn posthoc debug into a runtime rule.
- Do not treat `candidate_source_family` as a selector rule.
- Do not report only metrics without looking at the visual panels.
- Do not advance scoring before a human review sheet exists and is populated enough to justify the move.
- Do not mix synthesis mirror outputs with workspace audit outputs without explicitly labeling the source.
- Do not confuse partial factor tables with frozen ranked candidate tables.

## Output Contract

Every diagnostic run should produce:

- visual outputs
- `summary.json`
- report markdown
- missing fields/paths report
- input-source lineage note
- boundary check

Codex remains a local implementation assistant. Research conclusions must be supported by visual review plus accounting evidence.
