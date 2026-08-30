# Compatibility

## Supported matrix

| Surface | Supported versions or hosts | Notes |
| --- | --- | --- |
| Public Agent Skills | Agent Skills-compatible hosts that discover direct child `SKILL.md` files | Use the complete ten-skill collection for a new audit. |
| Installer | `npx skills` and native host installers | The repository does not require a custom registry or install path. |
| Python verifier | Python 3.11 and 3.12 | Standard library at runtime; `build` is only a development/release extra. |
| Operating systems | Windows, Linux, and macOS | Path and archive checks use platform-independent representations. |
| Python artifacts | Wheel and sdist | The wheel is optional verifier runtime; the skill archive is the portable methodology package. |

## Scope boundaries

The public product is the ten direct skills under `skills/`. The Python package
is optional infrastructure for deterministic protocol validation, fixture
evaluation, and release verification; it does not install the skills into an
agent and it does not replace a host's native installer.

The skills require an agent that can read and write files in the target project
and follow the host's Agent Skills discovery rules. The verifier cannot test
whether a particular host follows instructions correctly; that remains an
integration evaluation concern.

## Verification commands

From a source checkout:

```bash
python -m unittest discover -s tests -v
coherence validate-skills --json .
coherence eval --json .
coherence doctor --strict --json .
coherence release-check --json .
```

For a portable install check, use a fresh clone or the exact release URL:

```bash
npx skills add "https://github.com/MPSMeridiaN/Auditor" --skill '*' --copy --yes
```

## Untested combinations

Other Python versions, third-party Agent Skills hosts, network-restricted
package builds, and repositories containing unusual filesystem providers are
not promised by this matrix. Report a reproducible compatibility gap with the
host, operating system, version, command, and relevant verifier report.
