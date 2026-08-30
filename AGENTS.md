# AI Agent Installation Contract

This repository publishes the System Coherence Agent Skills suite. The
`skills/` tree is the product. `src/`, `tests/`, `examples/`, `scripts/`, and
the optional Python verifier are repository development surfaces, not runtime
dependencies of an installed skill.

When a user provides this repository URL and asks you to install and use
System Coherence, follow this contract:

1. Inspect the current coding-agent or harness environment. Identify its
   native skill installer, discovery command, supported installation scopes,
   and the target project.
2. Determine whether that environment supports Agent Skills natively. Prefer
   its native installer and discovery mechanism when it does.
3. If no native mechanism is available, use a compatible Agent Skills
   installer such as `npx skills` when it is available. Use the exact URL the
   user supplied; never invent an owner, repository slug, or filesystem path.
4. Before installing, list the repository's available skills. With `npx
   skills`, run `npx skills add <repository-url> --list` and inspect the
   result.
5. Treat the complete System Coherence suite as the normal installation. It
   contains 10 direct skills: `system-coherence` and its nine companion
   skills. The orchestrator's normal route requires those companions.
6. Choose project-local or global scope from the user's request and the
   harness context. With `npx skills`, run the complete install from the
   target project for project scope; add `--global` only for a user-wide
   request. If the harness requires a single agent target, pass its reported
   identifier with `--agent`; otherwise let the installer use its configured
   destinations. Do not hardcode `.agents/skills`, `.codex/skills`, or another
   agent's path when the installer already defines the destination.
7. Prefer copy semantics for a portable release check when the installer
   supports it (`--copy` with `npx skills`). If the harness uses links or its
   own managed storage, verify that the installed `SKILL.md`, references, and
   assets resolve from the installed location, not the source checkout.
8. Verify discovery after installation. Confirm that all required skill names
   are visible to the target agent and that the primary skill is the intended
   `system-coherence` entry point.
9. Verify the installed product's local runtime boundary: the primary
   `SKILL.md`, `references/artifact-protocol.md`, and the three JSON schemas
   are present beside it. Confirm that no source checkout is needed for these
   files.
10. Invoke `system-coherence` only after the installation and discovery checks
    pass. Run it with the target project in scope and let its `.coherence/`
    artifacts, not conversation history or the source checkout, drive the
    handoffs.

For a new audit, do not install only `system-coherence`; use the complete
suite. Install an individual specialist only when the user explicitly wants
that stage and its prerequisites already exist.

For later updates, use the selected installer's supported update mechanism.
With `npx skills`, use `npx skills update --project --yes` or
`npx skills update --global --yes`, matching the original scope. If update is
not supported, repeat the complete install from the new release source. Never
delete or replace the target project's `.coherence/` workspace when updating
the installed methodology.

Reusable user prompt:

```text
Install the System Coherence skill suite from <repository-url>.

Inspect the current coding-agent environment and use its native Agent Skills
installer/discovery mechanism when available. Otherwise use a compatible
Agent Skills installer. List the repository's skills before installing,
install the complete suite in the appropriate project or global scope, verify
every required skill and bundled reference is discoverable without the source
checkout, then invoke the primary system-coherence skill on this project.
Do not invent custom installation paths.
```
