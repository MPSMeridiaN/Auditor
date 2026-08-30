## Behavioral goal

Describe the user-visible behavior, invariant, or release boundary this change
addresses.

## Evidence and artifacts

- [ ] Relevant `.coherence/` artifacts or fixture evidence are current.
- [ ] Stable artifact IDs and protocol references are preserved or migrated.
- [ ] Remaining uncertainty and unsupported behavior are documented.

## Verification

- [ ] `python -m unittest discover -s tests -v`
- [ ] `coherence validate-skills --json .`
- [ ] `coherence eval --json .`
- [ ] `coherence doctor --strict --json .`
- [ ] `coherence release-check --json .` (when packaging or public skills are affected)
- [ ] `git diff --check`

## Security and distribution

- [ ] No secrets, absolute developer paths, symlinks, generated state, or
      credentials are included.
- [ ] The change keeps `skills/` self-contained and does not make it depend on
      the optional Python verifier or source checkout.
- [ ] Documentation, changelog, and compatibility notes are updated when the
      public contract changes.

## Limitations

List tests not run, host-agent integration gaps, or other remaining risks.
