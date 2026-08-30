---
name: reconstruct-system
description: Use when an unfamiliar repository needs an evidence-backed system model before capabilities, contracts, or implementation correctness can be audited.
---

# Reconstruct System

## Purpose

Describe what the target system actually contains and where its behavioral boundaries are. Separate observed architecture from intended behavior and do not treat current code as proof of correctness.

## Inputs

- `artifact/repository-evidence`.
- Targeted source, configuration, tests, and documentation selected from the evidence inventory.

## Required artifacts

- `.coherence/artifacts/repository-evidence.json` with a current or explicitly partial status.

## Optional context

- Runtime startup output, deployment manifests, user stories, external-system notes, or a requested subsystem.

## Outputs

- `artifact/system-model` with `system_id`, purpose, architecture style, components, interfaces, resources, boundaries, evidence references, and open questions.

## Artifacts modified

- `.coherence/artifacts/system-model.json`

## Completion criteria

- Each component has stable identity, kind, paths, and state authority where known.
- Each resource records representations, possible states, and authoritative owner when evidence supports it.
- UI, database, filesystem, queues, workers, IPC, caches, or external systems are included only when discovered.
- Every material assertion links to evidence; unresolved conflicts are explicit uncertainty.

## Failure / uncertainty behavior

- If evidence is missing or stale, stop and route to `system-coherence` for capture.
- If documentation and code conflict, record both sources and a `conflicting-evidence` entry.
- If a boundary cannot be observed, mark it unknown instead of filling it with a conventional architecture.
- A partial model may continue only with its gaps recorded in `uncertainty`.

## Next likely transitions

- Valid system model → `discover-capabilities`.
- Missing resource ownership → targeted reconstruction with a partial model.
- New source revision → `system-coherence` status, then scoped regression analysis if traces already exist.

## Procedure

1. Read the evidence inventory and identify the smallest set of source files, tests, configuration, and docs that can establish boundaries.
2. Determine runtime shape: desktop, web, CLI, library, service, worker, or distributed system; choose more than one only when evidence shows both.
3. List components and their communication edges. Mark state authority, derived views, persistence, external ownership, and process boundaries.
4. List resources and derive relevant environmental states from evidence; do not import a universal checklist.
5. Create stable `sys-`, component-, and resource-level IDs and attach `ev-` references rather than copying source blocks.
6. Write the complete envelope to the target repository's
   `.coherence/artifacts/system-model.json` with
   `producer.skill: reconstruct-system`, preserving uncertainty. If the
   optional verifier is available, pass the envelope to `coherence write` and
   run `coherence validate --json` against the target repository.

Example: a CLI with no database is modeled with command parsing, process state, filesystem resources, and exit/output observables; no UI or service layer is invented to make the model look complete.
