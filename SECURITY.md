# Security Policy

## Scope

System Coherence is an Agent Skills suite plus an optional local Python
verifier. It processes repositories that may be incomplete, adversarial, or
contain untrusted text. The installed skills use the target repository's
`.coherence/` directory as durable state.

The verifier treats the target repository as data for capture, validation, and
routing. It does not execute target source during those operations. The
evaluation command intentionally executes the small example fixtures, and
`release-check` intentionally invokes the packaging backend and installs built
artifacts; run those commands only in a checkout you trust.

## Trust boundaries

- Skill resources are self-contained below their owning `skills/<name>/`
  directory. Symlinked skill directories, protocol files, artifact paths, and
  evaluation fixtures are rejected.
- Artifact reads and writes must stay inside the target `.coherence/` workspace;
  path traversal and symlink escapes are errors.
- Release archives are inspected for unsafe paths, links, generated caches,
  high-confidence secret patterns, and absolute developer-machine paths.
- Reports can contain repository-derived text. Treat them as untrusted data and
  review before publishing them or feeding them to another automated system.

These checks reduce accidental leakage and confused-deputy behavior; they are
not a sandbox for arbitrary code. Use normal OS isolation for hostile code,
credentials, and build backends.

## Reporting a vulnerability

Please report security issues privately through a GitHub Security Advisory for
the repository, or contact a maintainer through the repository's private
security channel. Include a concise reproduction, affected version or commit,
impact, and any suggested mitigation. Do not include live credentials or
private repository contents in an issue.

If the report is accepted, maintainers will coordinate a fix, regression test,
release note, and disclosure timeline appropriate to the impact.

## Release hygiene

Every release should pass `coherence release-check`, the full test/evaluation
suite, and a clean-clone skill installation. Never commit `.coherence/`, build
outputs, credentials, or machine-local paths.
