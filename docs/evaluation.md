# Evaluation Methodology

The repository uses two complementary evaluation layers.

## Deterministic fixture evaluations

`coherence eval .` validates scenario metadata without importing repository
Python. `coherence eval --trusted-fixtures .` explicitly executes the declared
example fixtures and compares observable outcomes with scenario expectations.
Use the trusted mode only for a checkout whose code and build configuration are
trusted. Each scenario declares its capability IDs, whether it is a negative
control, and repository-relative evidence paths;
`skills/system-coherence/references/schemas/evaluation-scenarios.schema.json`
documents that metadata shape. The current suite includes:

| Scenario | Architecture | Defect exercised | Expected result |
| --- | --- | --- | --- |
| `web-cache-staleness` | Web application | Delete changes the database but not its derived cache | Detect `stale-derived-state` |
| `worker-partial-completion` | Worker/service | Completion is persisted before the side effect | Detect `partial-commit` |
| `clean-cli-rename` | CLI | Rename removes old identity and writes the new one | No finding (negative control) |

The probes verify behavior, not source strings. A fresh trusted run reports
three passed scenarios, two findings detected, and zero probe failures; the
default metadata-only run reports the scenarios as not run.

These evaluations demonstrate that the artifact framework can carry architecture-specific evidence and distinguish a lifecycle defect from correct behavior. They do not claim broad defect-detection coverage for arbitrary repositories.

## Protocol and graph tests

The standard-library test suite covers:

- stable IDs and timestamps;
- envelope status/field validation;
- atomic writes and hash-addressed history;
- file evidence and exclusions;
- resumable route selection;
- mapped and unknown invalidation;
- ledger precedence and closure after current revalidation;
- Agent Skills frontmatter, direct-directory discovery, and handoff sections;
- complete deterministic dogfood graph generation.
- symlink and path traversal rejection at artifact and fixture boundaries;
- release archive path, source-hygiene, and deterministic skill-archive checks;
- read-only doctor, route explanation, and findings reporting.

Run:

```bash
python -m unittest discover -s tests -v
```

## Host-agent skill evaluations

The Agent Skills are instructions consumed by a model. A host runtime with subagent/model access should add pressure scenarios for the skills, including stale evidence, incomplete traces, time pressure, conflicting sources, and the temptation to declare a transition verified without evidence. Those tests belong to the host integration because this repository's offline CLI cannot simulate every model's instruction-following behavior.

This boundary is a product limitation: structural validation does not imply
agent compliance. The deterministic dogfood state is generated in the checkout
and ignored; it is a protocol fixture, not a substitute for running the
installed skills against a target repository.

## Interpreting results

Protocol validation proves that artifacts are structurally and referentially coherent. Fixture evaluations prove the included probes reproduce the documented behaviors. A `verified` ledger entry means a current validation result exists with no open finding for that capability; it does not mean every possible state was explored. Read evidence, uncertainty, and coverage gaps alongside the ledger.

Packaging evaluation is a separate boundary: a passing release check proves
that the declared files can be built, inspected, and installed cleanly, not
that an arbitrary target repository or build backend is safe to execute.
