# Research Notes

System Coherence is intentionally an original composition of small, compatible ideas rather than a copy of another framework. The following primary sources informed the design.

## Sources and applied principles

### Agent Skills format and progressive disclosure

The [Agent Skills specification](https://agentskills.io/specification) defines a skill as a directory containing a required `SKILL.md`, with lowercase hyphenated names, YAML frontmatter, optional scripts/references/assets, and progressive disclosure from metadata to instructions to on-demand resources. System Coherence follows that shape and keeps each skill's contract in its main file while putting shared schemas and method details in repository documentation.

The [obra/superpowers repository](https://github.com/obra/superpowers) demonstrates a composable Markdown skill library with explicit engineering workflows, test/evaluation infrastructure, and a strong evidence-before-claims philosophy. System Coherence adopts the composability and pressure-tested workflow ideas, but gives its skills a domain-specific artifact protocol and a machine-readable orchestration layer.

### Behavioral and stateful testing

The [Hypothesis stateful testing documentation](https://hypothesis.readthedocs.io/en/latest/stateful.html) models tests as sequences of rules operating over a state machine, and stresses that actions can be chained so later actions depend on the current state. This supports System Coherence's separation of states, transitions, invariants, and adversarial lifecycle scenarios. The framework does not require Hypothesis: it records the same concepts in portable artifacts so an agent can derive tests in any target language.

### Provenance

The [W3C PROV-DM recommendation](https://www.w3.org/TR/prov-dm/) represents provenance with entities, activities, agents, derivations, and time. System Coherence uses the practical subset: evidence and artifacts are entities, skill runs are activities, the producing agent/runtime is recorded as the producer, and explicit `inputs`, `evidence_refs`, and `derived_from` links preserve derivation without requiring a graph database.

### Schema validation

The [JSON Schema 2020-12 guide](https://json-schema.org/UnderstandingJSONSchema.pdf) recommends the current draft and emphasizes schemas as executable examples of valid and invalid documents. System Coherence publishes JSON Schema documents for its envelopes and payload shapes, while its zero-dependency runtime performs the semantic checks needed for a useful CLI on a clean machine.

### Incremental invalidation

The [Bazel dependency-management documentation](https://bazel.build/basics/dependencies) explains why explicit, fine-grained dependency edges make it possible to avoid rebuilding or retesting unrelated work, while also warning about hidden transitive dependencies. System Coherence applies that lesson to behavioral knowledge: traces declare paths and the contracts/capabilities they cover; a change set walks those edges and invalidates only the affected verification state, with conservative escalation when a mapping is missing.

## Design consequences

1. Skills remain human-readable Markdown, but every handoff is a validated JSON artifact envelope.
2. The current artifact is easy to inspect; previous versions are addressed by content hash and provenance metadata rather than a database migration.
3. Stable IDs identify domain entities such as capabilities, contracts, transitions, traces, and findings. Artifact snapshots have stable logical addresses plus revision/content metadata.
4. The CLI is a protocol assistant, not an LLM replacement. It captures repository evidence, validates handoffs, routes the next skill, computes scoped invalidation, and renders the ledger. Agents still perform the repository-specific behavioral reasoning described by the skills.
5. Missing architecture layers are represented as empty or not-applicable components in the system model, never invented merely to satisfy a checklist.

