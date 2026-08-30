# Getting started

System Coherence has two surfaces:

1. the portable Agent Skills collection under `skills/`; and
2. an optional Python verifier for contributors and deterministic checks.

Install the first surface into the repository you want to audit. The second
surface is not required by the installed skills.

For the concise URL-only instructions intended for a coding agent, see the
[AI Agent Installation Contract](../AGENTS.md).

## Install the skills

### Recommended: complete collection

From the target repository, install from the exact public repository URL:

```bash
npx skills add "<repository-url>" --skill '*' --copy --yes
```

The public tree contains 10 direct skills. The complete collection is required
for a new end-to-end audit because `system-coherence` hands off to the other
nine skills. `--copy` makes the installed files independent of the source
checkout. The installer chooses its configured agent destinations; pass
`--agent <host-agent-id>` when the harness requires one specific destination.

For global scope, add `--global`:

```bash
npx skills add "<repository-url>" --skill '*' --agent <host-agent-id> --copy --global --yes
```

Use the agent identifier reported by the current harness. Targeting one agent
avoids partial global installs when a machine has configured destinations that
do not support global skills.

For a deliberately focused stage, install one specialist explicitly:

```bash
npx skills add "<repository-url>" --skill audit-coherence --copy --yes
```

Use the harness's native installer when it provides one. Otherwise, `npx
skills` is the compatible fallback. Do not invent a skills directory or copy
only the orchestrator for a new audit. If the repository has not been
published yet, use a clean clone of the release tree as the source and replace
`<repository-url>` with the resulting public URL before sharing the docs.

After installation, verify discovery through the host's native listing. With
`npx skills`, use `npx skills ls --json` and confirm all 10 names are present;
also confirm that `system-coherence/SKILL.md` can read its local
`references/` directory. The optional Python verifier is not part of this
runtime check.

When the installer records the source, receive project-local updates with:

```bash
npx skills update --project --yes
```

Use `npx skills update --global --yes` for global scope. If update is not
supported by the selected host, repeat the complete install command. Both
paths update the installed methodology, not the target's `.coherence/` state.

If no compatible installer exists, follow the host's documented manual
installation path. Preserve each direct skill and keep
`system-coherence/references/` beside its `SKILL.md`; do not assume that any
particular agent's filesystem path is universal.

## Start the first audit

Invoke `system-coherence` with the target repository in scope. Use the same
request for a new or existing workspace:

```text
Run a System Coherence audit of this repository. Start from the current
.coherence state if one exists, otherwise initialize it. Continue through the
available stages, preserve evidence for every conclusion, and tell me the
next safe step when a handoff is incomplete.
```

The orchestrator first reads `.coherence/artifacts/` and then selects one next
skill. The first run normally captures `repository-evidence`; later handoffs
produce the system model, capability map, behavioral contracts, state model,
implementation traces, findings, remediation, regression scope, validation,
and the Coherence Ledger.

If the session stops halfway through, invoke `system-coherence` again. The
current artifact files are the handoff; the previous conversation is not a
prerequisite.

## Inspect the target workspace

The installed skills write only to the target repository:

```text
target-repository/.coherence/
├── config.json
├── session.json
├── evidence/
├── artifacts/
│   ├── repository-evidence.json
│   ├── system-model.json
│   ├── capability-map.json
│   ├── behavioral-contracts.json
│   ├── state-model.json
│   ├── implementation-traces.json
│   ├── audit-findings.json
│   ├── intervention-plan.json
│   ├── regression-scope.json
│   ├── revalidation-results.json
│   └── coherence-ledger.json
├── history/
└── tmp/
```

Read the [artifact protocol](../skills/system-coherence/references/artifact-protocol.md)
when constructing or extending an envelope. It defines the stable IDs,
source revisions, evidence references, freshness, uncertainty, and cross-file
links required for a durable handoff.

## Optional verifier

From this source checkout, install the contributor tool with Python 3.11+:

```bash
python -m pip install -e .
coherence init /path/to/target
coherence status --json /path/to/target
coherence route --json /path/to/target
```

For a changed implementation, capture evidence, calculate scope, and refresh
the ledger:

```bash
coherence capture /path/to/target
coherence invalidate /path/to/target src/domain/delete.py src/cache.py
coherence ledger --json /path/to/target
```

The verifier validates the protocol and makes routing deterministic; it does
not simulate the host agent's reasoning. The skills remain usable without it.

## Verify this checkout

Run the development gates from the source checkout:

```bash
python -m unittest discover -s tests -v
coherence validate-skills --json .
coherence eval --json .
python scripts/dogfood.py
coherence validate --json .
coherence route --json .
```

The generated root `.coherence/` directory is ignored. It is a disposable
protocol fixture for this checkout, not a completed audit or part of the
public skill collection.
