# Security Policy

## Scope

System Coherence is an Agent Skills suite plus an optional local Python
verifier. It processes repositories that may be incomplete, adversarial, or
contain untrusted text. The installed skills use the target repository's
`.coherence/` directory as durable state.

The verifier treats the target repository as data for capture, validation, and
routing. It does not execute target source during those operations. The default
evaluation command validates metadata only; `--trusted-fixtures` explicitly
executes the small example fixtures. `release-check` invokes the packaging
backend, scans public Git history, and installs built artifacts. Run those
execution paths only in a checkout you trust.

## Trust boundaries

- Skill resources are self-contained below their owning `skills/<name>/`
  directory. Symlinked skill directories, protocol files, artifact paths, and
  evaluation fixtures are rejected.
- Artifact reads and writes must stay inside the target `.coherence/` workspace;
  path traversal and symlink escapes are errors.
- Release archives are inspected for unsafe paths, links, generated caches,
  high-confidence secret patterns, and absolute developer-machine paths.
- Public Git refs are scanned for non-public commit-email identities and the
  same high-confidence secret/path patterns. Findings are redacted to
  commit IDs, domains, paths, and pattern names.
- Scenario modules must live below `examples/`; importing them requires the
  explicit trusted-fixtures opt-in.
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
outputs, credentials, machine-local paths, or personal commit addresses. Use a
GitHub no-reply address for public history; a history rewrite cannot remove
copies already retained by remote caches or downstream clones.
