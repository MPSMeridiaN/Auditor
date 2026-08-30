# Changelog

All notable changes to the System Coherence suite are documented here. The
repository is the source of truth for the published skill tree; Python package
versions and Git tags use the same semantic version.

## [1.2.0] - 2026-08-30

### Added

- Explicit trusted-fixture opt-in for executable evaluations; default evaluation
  validates metadata without importing repository code.
- Strict artifact JSON parsing, methodology-version provenance, input-cycle
  detection, orphaned-workspace checks, and stronger published schemas.
- Public documentation-link, package-boundary, archive-duplicate, and Git
  history privacy checks in the release gate.
- False-positive, protocol-issue, and host-compatibility issue templates.

### Changed

- Source distributions now contain only the optional verifier and packaging
  metadata; skills ship as a separate deterministic archive.
- Release builds use a single runtime version source, current action runtimes,
  atomic release outputs, and conservative failure behavior.

## [1.1.0] - 2026-08-30

### Added

- Read-only `coherence doctor`, `explain`, and `findings` commands for safe
  environment diagnostics and artifact-driven routing.
- `coherence release-check` for source hygiene, skill-tree validation, wheel
  and sdist boundary checks, clean installs, deterministic skill archives,
  checksums, and machine-readable reports.
- Symlink and path-boundary checks for target artifacts, evaluation fixtures,
  and public skill resources.
- Compatibility, security, case-study, issue-template, pull-request, and
  automated release documentation.

### Changed

- The optional Python verifier now has an explicit package version, project
  URLs, and a clean source-distribution build boundary.
- Release automation publishes only after tests, evaluations, packaging,
  clean-install, and skill-discovery checks pass.

## [1.0.1] - 2026-08-29

- Fixed release checks to use portable byte-length assertions across operating
  systems.
- Published the canonical repository URL and version-consistency checks.

## [1.0.0] - 2026-08-29

- Initial public release of the ten-skill System Coherence suite and optional
  standard-library verifier.

[1.1.0]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.1.0
[1.2.0]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.2.0
[1.0.1]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.0.1
[1.0.0]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.0.0
