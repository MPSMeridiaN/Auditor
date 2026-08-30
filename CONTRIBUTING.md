# Contributing

Contributions should preserve the principle that the repository is the shared memory and artifacts are the communication protocol.

## Development setup

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
coherence validate-skills --json .
coherence eval .
```

Python runtime code uses the standard library only. Keep tests runnable on Python 3.11+ and use forward-slash paths in skill documentation.

## Changes

- Start from a feature branch.
- Add a failing test before production behavior changes.
- Keep artifact IDs stable and update protocol docs/schema when contracts change.
- Add evidence and uncertainty rather than hiding conflicts.
- Run dogfood after changes to the orchestration or skill protocol.
- Run `git diff --check` before committing.

For a new skill, follow [docs/extension-guide.md](docs/extension-guide.md). Keep it as a direct `skills/<name>/SKILL.md` sibling, bundle any required resources under that skill, and validate the collection with `coherence validate-skills --json .` from a source checkout.

## Pull requests

Describe the behavioral goal, artifacts touched, evidence, tests, evaluation output, and any remaining limitations. Do not claim a capability is verified without a current revalidation result and evidence references.
