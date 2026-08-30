# Architecture

System Coherence has two deliberately separate surfaces:

1. a standard Agent Skills collection under `skills/`; and
2. an optional standard-library Python verifier under `src/coherence/` used by
   repository contributors and deterministic evaluations.

The skills decide what to inspect and what behavior means. The verifier makes
their handoffs durable, validated, routable, and incrementally invalidatable
when it is available. Neither surface stores audit state in this repository's
skill directories.

## Public skill collection

Every independently invokable skill is a direct child of `skills/` with a
required `SKILL.md`. `system-coherence` is the orchestrator; the other nine
directories are specialists. The host's normal Agent Skills discovery scans
these siblings, and `npx skills add` copies or links them without reading a
custom manifest.

The orchestrator owns its protocol reference and schemas in
`skills/system-coherence/references/`. This keeps material needed to
understand an envelope with the skill that introduces the workflow. No public
skill requires a root-relative documentation, source, or build path.

## Optional verifier components

| Component | Responsibility | Durable boundary |
| --- | --- | --- |
| `coherence.evidence` | Inventory files, hashes, languages, and git revision | `repository-evidence` |
| `coherence.schema` | Validate envelope shape and semantic payload requirements | errors list |
| `coherence.store` | Atomic snapshots, hashes, history, and cross-artifact references | target `.coherence/artifacts/` |
| `coherence.workflow` | Stage registry, prerequisite checks, and routing decisions | route JSON |
| `coherence.invalidation` | Changed-path mapping and conservative scope | `regression-scope` |
| `coherence.ledger` | Capability status derivation | `coherence-ledger` |
| `coherence.skills` | Direct `SKILL.md` frontmatter and handoff validation | skill directory scan |
| `coherence.evaluation` | Executable development fixture probes | evaluation report |
| `coherence.doctor` | Read-only environment and workspace diagnostics | diagnostic report |
| `coherence.release` | Source, archive, package, and clean-install gates | release report and checksums |

## Source and distribution boundaries

The repository intentionally carries more than the runtime skill package:

| Surface | Contains | Distribution rule |
| --- | --- | --- |
| `skills/` | Ten `SKILL.md` files and orchestrator protocol resources | Copied by an Agent Skills installer; no Python dependency. |
| `src/coherence/` | Optional verifier implementation | Included in the wheel and sdist only. |
| `tests/`, `examples/`, `docs/`, `scripts/` | Development, evaluation, and contributor material | Source-checkout only; excluded from the wheel, sdist, and skill archive. |
| `.coherence/`, `.agents/`, `build/`, `dist/`, reports | Generated target or build state | Ignored and rejected from runtime/release boundaries. |

`coherence release-check` builds in a clean staging tree so a local cache
cannot silently change the source archive. It rejects unsafe paths, links,
generated metadata, high-confidence secret patterns, and absolute developer
machine paths before release assets are produced.

## Stage boundaries

Each stage has one job, reads named inputs, and writes one logical output. A
stage can continue from a partial artifact only when its uncertainty is
explicit; blocked, stale, invalid, or missing prerequisites route back to the
appropriate producer.

```text
capture → reconstruct → discover → contract → states → trace → audit
                                                               ↓
                                                     remediation
                                                               ↓
                                            regression → revalidate → ledger
```

The Python stage registry is a verifier convenience. The installed
`system-coherence` skill also carries an explicit route table so orchestration
can resume from target files without importing Python or reading conversation
history.

The verifier's `doctor`, `explain`, and `findings` commands are read-only. The
default `eval` command validates scenario metadata without importing target
Python; `--trusted-fixtures` explicitly opts into executing declared example
fixtures. The release checker invokes the packaging backend, scans public Git
history, and installs artifacts in disposable environments. These execution
paths require a trusted checkout.

## Target workspace and resumption

The current artifact address is stable (`artifact/<artifact-type>`), while
`source_revision`, `content_hash`, `run_id`, and provenance identify a
particular snapshot. The target repository owns `.coherence/`; its current
snapshots live in `.coherence/artifacts/`, and optional hash-addressed history
is kept below `.coherence/history/`.

`coherence status --json` combines present snapshot metadata, validation errors,
and the next route. `coherence route --json` compares stored evidence with the
live source tree. A changed tree routes to evidence capture unless a current
regression scope explicitly covers that snapshot. No route depends on an
in-memory session.

## Invalidation

Implementation traces expose source path patterns and entry points.
`coherence invalidate` matches changed paths against those patterns, walks
trace → contract → capability links, and creates a regression scope. A path
with no mapping becomes a scope-unknown condition and requests broad
revalidation. A path change marks only the affected verification state stale.

## Development boundary

`tests/`, `examples/`, `scripts/dogfood.py`, and `.github/` exercise the
optional verifier and public collection. A dogfood run may create a local
`.coherence/` protocol fixture, but the directory is generated target state
and is ignored rather than committed or packaged with the skills.
