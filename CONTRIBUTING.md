# Contributing

Contributions should preserve the principle that the repository is the shared memory and artifacts are the communication protocol.

## Development setup

```bash
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
coherence validate-skills --json .
coherence eval --trusted-fixtures .
coherence doctor --strict --json .
coherence release-check --json .
```

Python runtime code uses the standard library only. Keep tests runnable on Python 3.11+ and use forward-slash paths in skill documentation.

## Changes

- Start from a short-lived branch based on `main`.
- Add a failing test before production behavior changes.
- Keep artifact IDs stable and update protocol docs/schema when contracts change.
- Add evidence and uncertainty rather than hiding conflicts.
- Run dogfood after changes to the orchestration or skill protocol.
- Run `git diff --check` before committing.
- Keep the public skill tree separate from the optional Python verifier and
  never commit `.coherence/`, build output, reports, credentials, or local
  machine paths.
- The wheel and sdist contain only the optional verifier; the ten-skill archive
  is built separately. Run `coherence release-check` to verify both boundaries.

For a new skill, follow [docs/extension-guide.md](docs/extension-guide.md). Keep it as a direct `skills/<name>/SKILL.md` sibling, bundle any required resources under that skill, and validate the collection with `coherence validate-skills --json .` from a source checkout.

## Pull requests

Describe the behavioral goal, artifacts touched, evidence, tests, evaluation output, and any remaining limitations. Do not claim a capability is verified without a current revalidation result and evidence references.

Release-oriented changes must also describe the wheel/sdist boundary, skill
archive contents, clean-install result, and whether the public version or
changelog changed. The release workflow publishes only from a version tag after
the complete verification job passes.
