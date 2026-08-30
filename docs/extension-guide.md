# Extension Guide

System Coherence grows as a flat Agent Skills collection. Add a specialist
only when it has a distinct trigger, durable handoff, and independently useful
reasoning boundary.

## Add a skill

1. Create `skills/<lowercase-hyphen-name>/SKILL.md` directly under `skills/`.
2. Use frontmatter with matching `name` and a description beginning with
   `Use when`.
3. Declare `Purpose`, `Inputs`, `Required artifacts`, `Optional context`,
   `Outputs`, `Artifacts modified`, `Completion criteria`, `Failure /
   uncertainty behavior`, and `Next likely transitions`.
4. Write and read artifacts only in the target repository's `.coherence/`
   workspace. Never use the installed skill directory as runtime state.
5. Put reusable tools, templates, schemas, or heavy references under that
   skill's own `scripts/`, `assets/`, or `references/` directory.
6. Run `coherence validate-skills --json .` from a source checkout. This
   verifier scans direct child directories; no manifest entry is needed.

Keep `SKILL.md` under 500 lines. Use relative references from the skill root
and keep reference chains one level deep. A skill may mention the optional
`coherence` verifier for deterministic validation, but it must remain readable
and resumable when that command is absent.

## Add or change a routed stage

The standard Agent Skills surface is still the skill directory. Only the
optional verifier needs a stage-registry change in
`src/coherence/workflow.py`. Add a failing verifier test first, update the
registry and route behavior, then update the affected skill's handoff and
documentation. Preserve stable artifact IDs and make the new route explainable
from `.coherence/` snapshots alone.

## Add fields to an artifact

Describe the field in the producing skill and the protocol reference bundled
with `skills/system-coherence/references/`. If it is required for protocol
integrity, update the corresponding local JSON Schema and the optional
verifier's semantic checks, then add a failing test before implementation. If
it is interpretive, preserve unknown fields and document their provenance
meaning without making unrelated artifacts depend on them.

## Add a target architecture adapter

Adapters translate architecture-specific evidence into the same model:

- identify actual components and authorities;
- map interfaces to capabilities;
- map resources and operations to states/transitions;
- emit source/runtime evidence IDs;
- leave unsupported layers absent rather than inventing them.

Keep adapter scripts and references inside the skill that invokes them. The
adapter must write the standard envelope into the target `.coherence/`
workspace and remain independently resumable.

## Add an evaluator

Add an executable fixture under `examples/<architecture>/`, a scenario in
`examples/scenarios.json`, and a probe in `src/coherence/evaluation.py`. These
are development/evaluation files, not skill runtime dependencies. The scenario
must declare capability IDs, its `negative_control` flag, and repository-
relative evidence paths that exist. The probe must exercise observable
behavior, and a negative control should accompany rules that could over-report.

Run metadata validation by default and execute fixtures only with the explicit
`coherence eval --trusted-fixtures` flag from a trusted checkout. Document both
what the evaluation proves and what it cannot prove. Host-agent
instruction-following tests belong to the host integration because the offline
verifier cannot simulate every model.

Before proposing a release, run `coherence release-check --json .`. It verifies
that the public skill tree remains exact, local skill references resolve after
copying, source archives do not contain generated state or unsafe links, and
the optional Python package imports from both wheel and sdist in clean
environments. Treat the generated checksum and JSON report as release evidence
rather than committed source files.

## Preserve compatibility

Do not change stable IDs or artifact names casually. If a breaking payload
change is necessary, increment `schema_version`, provide migration guidance,
and keep old-reader behavior explicit. Prefer additive fields and conservative
unknown handling.
