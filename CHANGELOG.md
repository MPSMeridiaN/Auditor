# Changelog

All notable changes to the System Coherence suite are documented here. The
repository is the source of truth for the published skill tree; Python package
versions and Git tags use the same semantic version.

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
[1.0.1]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.0.1
[1.0.0]: https://github.com/MPSMeridiaN/Auditor/releases/tag/v1.0.0
