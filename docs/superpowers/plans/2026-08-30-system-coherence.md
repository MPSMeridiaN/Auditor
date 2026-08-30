# System Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable Agent Skills-compatible behavioral coherence framework with a validated artifact workspace, resumable routing, scoped invalidation, examples, evaluations, and self-audit evidence.

**Architecture:** A Python 3.11+ standard-library package owns stable IDs, JSON envelope validation, atomic artifact storage, repository evidence capture, workflow routing, invalidation, and ledger derivation. Markdown `SKILL.md` directories provide the specialist reasoning operators and reference the same protocol. The root `.coherence/` workspace is a checked-in, inspectable dogfood run; generated history remains ignored.

**Tech Stack:** Python 3.11+; standard library only at runtime; `unittest`; `pyproject.toml` with a console-script entry point; JSON Schema 2020-12 documents; Markdown Agent Skills.

**Spec:** `docs/superpowers/specs/2026-08-30-system-coherence-design.md`

## Global Constraints

- Use Python `>=3.11` and no mandatory runtime dependencies.
- Preserve the repository as the shared memory; no skill may require conversation history.
- Every current artifact is a JSON envelope with explicit `artifact_type`, `schema_version`, stable `artifact_id`, `run_id`, `status`, `source_revision`, `producer`, `inputs`, `evidence_refs`, `uncertainty`, `freshness`, and `content`.
- Use statuses `complete`, `partial`, `blocked`, `stale`, and `invalid` for artifact envelopes.
- Use deterministic domain IDs (`cap-`, `con-`, `trn-`, `trc-`, `fnd-`, `act-`, `val-`, `ev-`) so references survive revisions.
- Write artifacts atomically and preserve prior versions by content hash under `.coherence/history/` without committing generated history.
- Keep `SKILL.md` files compatible with the Agent Skills specification: lowercase hyphenated directory/name, required `name` and `description` frontmatter, and explicit handoff sections.
- Tests must run with `python -m unittest discover -s tests -v` after `python -m pip install -e .` or with `PYTHONPATH=src` from a checkout.

---

### Task 1: Establish package, models, and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/coherence/__init__.py`
- Create: `src/coherence/__main__.py`
- Create: `src/coherence/models.py`
- Test: `tests/test_models.py`
- Test: `tests/__init__.py`

**Interfaces:**
- Produces `coherence.models.stable_id(prefix: str, seed: str) -> str`.
- Produces `coherence.models.utc_now() -> str` with a UTC ISO-8601 `Z` suffix.
- Produces immutable stage/status constants used by later tasks.
- The package version is `0.1.0`; the console script is `coherence = coherence.cli:main`.

- [ ] **Step 1: Write the failing model tests**

```python
from coherence.models import ARTIFACT_STATUSES, stable_id, utc_now

def test_stable_id_is_deterministic_and_prefixed():
    assert stable_id("cap", "delete a file") == stable_id("cap", "delete a file")
    assert stable_id("cap", "delete a file").startswith("cap-")
    assert stable_id("cap", "delete a file") != stable_id("cap", "rename a file")

def test_utc_now_is_machine_sortable():
    assert utc_now().endswith("Z")
    assert "T" in utc_now()
    assert set(ARTIFACT_STATUSES) == {"complete", "partial", "blocked", "stale", "invalid"}
```

- [ ] **Step 2: Run the model tests and verify the expected import failure**

Run: `python -m unittest tests.test_models -v`

Expected: FAIL because `coherence.models` does not exist yet.

- [ ] **Step 3: Implement the smallest package surface**

```python
def stable_id(prefix: str, seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

- [ ] **Step 4: Run the model tests and full empty harness**

Run: `python -m unittest tests.test_models -v`

Expected: PASS with two tests and no warnings.

Run: `python -m unittest discover -s tests -v`

Expected: PASS with the same two tests.

- [ ] **Step 5: Commit the package foundation**

```text
git add pyproject.toml src/coherence tests
git commit -m "feat: add coherence package foundation"
```

---

### Task 2: Implement envelope contracts, payload validation, and artifact storage

**Files:**
- Create: `src/coherence/schema.py`
- Create: `src/coherence/store.py`
- Create: `schemas/artifact-envelope.schema.json`
- Create: `schemas/artifact-payloads.schema.json`
- Create: `tests/helpers.py`
- Test: `tests/test_artifacts.py`

**Interfaces:**
- `schema.validate_envelope(value: dict, expected_type: str | None = None) -> list[str]` returns an empty list for valid input.
- `store.Workspace(root: Path)` discovers `.coherence/`, `artifacts/`, and `evidence/`.
- `store.ArtifactStore(workspace).write(envelope: dict) -> Path` validates, hashes, archives, and atomically replaces the current artifact.
- `store.ArtifactStore.read(artifact_type: str) -> dict | None` reads the current snapshot.
- `store.ArtifactStore.validate_all() -> dict[str, list[str]]` reports per-artifact errors.
- `tests.helpers.valid_envelope(artifact_type: str, content: dict, **overrides) -> dict` supplies valid test envelopes.

- [ ] **Step 1: Write failing contract and storage tests**

```python
def test_rejects_missing_required_envelope_fields():
    errors = validate_envelope({"artifact_type": "system-model"})
    assert "missing required field: schema_version" in errors

def test_writes_and_reads_an_atomic_current_artifact(tmp_path):
    store = ArtifactStore(Workspace(tmp_path))
    envelope = valid_envelope("system-model", {"system_id": "sys-demo"})
    path = store.write(envelope)
    assert path.name == "system-model.json"
    assert store.read("system-model")["content"]["system_id"] == "sys-demo"
    assert store.validate_all() == {}

def test_rejects_unknown_artifact_type(tmp_path):
    store = ArtifactStore(Workspace(tmp_path))
    with self.assertRaises(ValueError):
        store.write(valid_envelope("unknown", {}))
```

The actual test uses `unittest.TestCase.assertRaises`; it must not depend on pytest.

- [ ] **Step 2: Run the artifact tests and verify they fail for missing modules/behavior**

Run: `python -m unittest tests.test_artifacts -v`

Expected: FAIL because the validator/store interfaces are not implemented.

- [ ] **Step 3: Implement envelope semantics**

Validate required fields, legal statuses, exact artifact type names, stable logical IDs (`artifact/<type>`), list-shaped `inputs`, `evidence_refs`, and `uncertainty`, freshness state, and a dictionary `content`. Validate cross-object IDs for each known payload type and reject dangling references.

- [ ] **Step 4: Implement atomic storage and content hashing**

Create `.coherence/artifacts`, `.coherence/evidence`, `.coherence/history`, and `.coherence/tmp`. Serialize with sorted keys and two-space indentation. Write a temporary file in the target directory, flush it, replace the current file, and copy the previous current snapshot to `.coherence/history/<artifact-type>/<content-hash>.json` when it differs.

- [ ] **Step 5: Run artifact tests, then the full suite**

Run: `python -m unittest tests.test_artifacts -v`

Expected: PASS for missing fields, valid round-trip, unknown type rejection, and history behavior.

Run: `python -m unittest discover -s tests -v`

Expected: all model and artifact tests pass.

- [ ] **Step 6: Commit the protocol core**

```text
git add src/coherence/schema.py src/coherence/store.py schemas tests/test_artifacts.py
git commit -m "feat: add validated artifact workspace"
```

---

### Task 3: Add deterministic repository evidence capture and initialization

**Files:**
- Create: `src/coherence/evidence.py`
- Create: `src/coherence/config.py`
- Create: `src/coherence/cli.py`
- Modify: `src/coherence/__main__.py`
- Test: `tests/test_evidence.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- `evidence.capture(root: Path) -> dict` returns a valid `repository-evidence` envelope.
- `evidence.classify_path(path: Path) -> str` returns `source`, `test`, `docs`, `config`, `asset`, `generated`, or `other`.
- `cli.main(argv: list[str] | None = None) -> int` implements `init`, `capture`, `write`, `validate`, and `route` command dispatch.
- `coherence init [ROOT]` creates config/session directories and captures evidence.

- [ ] **Step 1: Write failing evidence tests**

```python
def test_capture_hashes_files_and_excludes_coherence_and_git(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".coherence").mkdir()
    (tmp_path / ".coherence" / "secret.txt").write_text("ignore", encoding="utf-8")
    envelope = capture(tmp_path)
    paths = {item["path"] for item in envelope["content"]["files"]}
    assert "src/app.py" in paths
    assert ".coherence/secret.txt" not in paths

def test_init_command_creates_workspace_and_evidence(tmp_path):
    assert main(["init", str(tmp_path)]) == 0
    assert (tmp_path / ".coherence" / "config.json").exists()
    assert (tmp_path / ".coherence" / "artifacts" / "repository-evidence.json").exists()
```

- [ ] **Step 2: Run the evidence tests and verify they fail**

Run: `python -m unittest tests.test_evidence tests.test_cli -v`

Expected: FAIL because capture and CLI dispatch are absent.

- [ ] **Step 3: Implement file inventory and revision detection**

Walk the root without following directory symlinks; exclude `.git`, `.coherence`, `.agents`, common build/cache directories, and the artifact output itself. Record POSIX relative path, byte size, SHA-256, classification, and a best-effort language. Use `git rev-parse HEAD` when available; otherwise use `WORKTREE`.

- [ ] **Step 4: Implement CLI workspace setup and write path**

Create `config.json` with protocol version and root marker, `session.json` with a run ID and timestamps, and write the captured evidence through `ArtifactStore`. `write` accepts a JSON file containing an envelope, validates it, and stores it. All CLI errors go to stderr and return non-zero without a traceback for user input errors.

- [ ] **Step 5: Run evidence, CLI, and full tests**

Run: `python -m unittest tests.test_evidence tests.test_cli -v`

Expected: PASS with file hashes, exclusions, initialization, JSON output, and invalid-input error tests.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 6: Commit evidence capture**

```text
git add src/coherence/evidence.py src/coherence/config.py src/coherence/cli.py src/coherence/__main__.py tests
git commit -m "feat: capture repository evidence from the CLI"
```

---

### Task 4: Implement workflow registry, resumable routing, ledger derivation, and invalidation

**Files:**
- Create: `src/coherence/workflow.py`
- Create: `src/coherence/invalidation.py`
- Create: `src/coherence/ledger.py`
- Modify: `src/coherence/cli.py`
- Test: `tests/test_workflow.py`
- Test: `tests/test_invalidation.py`
- Test: `tests/test_ledger.py`

**Interfaces:**
- `workflow.route(store: ArtifactStore) -> dict` returns `skill`, `stage`, `reason`, `required_artifacts`, `produces`, and `context_paths`.
- `workflow.validate_graph(store: ArtifactStore) -> list[str]` reports missing/invalid/stale prerequisites.
- `invalidation.changed_paths(root: Path, base: str | None, explicit: list[str]) -> list[str]` resolves a deterministic change set.
- `invalidation.compute_scope(store, paths, source_revision) -> dict` returns a `regression-scope` envelope.
- `ledger.derive(store) -> dict` returns a `coherence-ledger` envelope from capabilities, contracts, findings, and validations.

- [ ] **Step 1: Write failing routing tests**

```python
def test_route_after_init_selects_system_reconstruction(tmp_path):
    main(["init", str(tmp_path)])
    result = route(ArtifactStore(Workspace(tmp_path)))
    assert result["skill"] == "reconstruct-system"
    assert result["required_artifacts"] == ["repository-evidence"]

def test_route_reports_blocked_prerequisite(tmp_path):
    write_blocked_evidence(tmp_path)
    result = route(ArtifactStore(Workspace(tmp_path)))
    assert result["reason"] == "required artifact is blocked"
```

- [ ] **Step 2: Run routing tests and verify they fail**

Run: `python -m unittest tests.test_workflow -v`

Expected: FAIL because no stage registry or route logic exists.

- [ ] **Step 3: Implement the explicit stage registry**

Register the ten stages from the spec with exact artifact inputs/outputs and skill names. Treat `partial` as resumable with declared uncertainty, and treat `blocked`, `invalid`, or `stale` prerequisites as repair routes. Report the first missing artifact in canonical order.

- [ ] **Step 4: Write failing invalidation and ledger tests**

```python
def test_changed_trace_path_invalidates_only_linked_capability(tmp_path):
    seed_complete_workspace(tmp_path)
    scope = compute_scope(store, ["src/cache.py"], "rev-2")
    assert scope["content"]["impacted_capability_ids"] == ["cap-cache"]
    assert "con-cache" in scope["content"]["invalidated_contract_ids"]

def test_high_open_finding_makes_ledger_capability_broken(tmp_path):
    seed_findings_workspace(tmp_path, severity="high", status="open")
    ledger = derive(store)
    assert ledger["content"]["entries"][0]["status"] == "broken"
```

- [ ] **Step 5: Run invalidation and ledger tests and verify the expected failures**

Run: `python -m unittest tests.test_invalidation tests.test_ledger -v`

Expected: FAIL because scope walking and status derivation are absent.

- [ ] **Step 6: Implement path-to-trace-to-contract-to-capability invalidation**

Match normalized changed paths against trace `source_paths` and `entrypoints`. For unmapped paths, emit `scope-unknown` with `requires_broad_revalidation: true`. Mark affected ledger entries `needs-revalidation`, preserve the prior finding IDs, and mark existing revalidation results stale. Persist the scope through `ArtifactStore`.

- [ ] **Step 7: Implement ledger derivation and CLI commands**

Derive one entry per capability, compute the status precedence described in the spec, carry last verified revision and evidence references, and render both concise text and `--json`. Add `status`, `route`, `invalidate`, and `ledger` subcommands.

- [ ] **Step 8: Run all workflow tests**

Run: `python -m unittest tests.test_workflow tests.test_invalidation tests.test_ledger -v`

Expected: PASS with mapped and unknown changes, status precedence, and resumable routing.

- [ ] **Step 9: Commit orchestration state**

```text
git add src/coherence/workflow.py src/coherence/invalidation.py src/coherence/ledger.py src/coherence/cli.py tests
git commit -m "feat: add resumable routing and scoped invalidation"
```

---

### Task 5: Publish Agent Skills and validate their contracts

**Files:**
- Create: `skills/system-coherence/SKILL.md`
- Create: `skills/reconstruct-system/SKILL.md`
- Create: `skills/discover-capabilities/SKILL.md`
- Create: `skills/model-behavior/SKILL.md`
- Create: `skills/model-states/SKILL.md`
- Create: `skills/trace-implementation/SKILL.md`
- Create: `skills/audit-coherence/SKILL.md`
- Create: `skills/plan-remediation/SKILL.md`
- Create: `skills/analyze-regression/SKILL.md`
- Create: `skills/revalidate-coherence/SKILL.md`
- Create: `skills/manifest.json`
- Modify: `src/coherence/cli.py`
- Modify: `src/coherence/workflow.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Every skill declares `Purpose`, `Inputs`, `Required artifacts`, `Optional context`, `Outputs`, `Artifacts modified`, `Completion criteria`, `Failure / uncertainty behavior`, and `Next likely transitions`.
- `coherence validate-skills` returns zero only when frontmatter, directory/name matching, manifest entries, and required contract headings are valid.
- Skill procedures always read current artifacts before writing and reference stable IDs/evidence rather than copying large source blocks.

- [ ] **Step 1: Write failing skill validation tests**

```python
def test_all_published_skills_have_spec_frontmatter_and_contract_sections():
    errors = validate_skill_tree(PROJECT_ROOT / "skills")
    self.assertEqual(errors, [])

def test_validator_catches_directory_name_mismatch(tmp_path):
    make_skill(tmp_path / "BadName", "name: different\ndescription: x\n")
    self.assertIn("name must match directory", validate_skill_tree(tmp_path)[0])
```

- [ ] **Step 2: Run the skill tests against the empty tree and verify failure**

Run: `python -m unittest tests.test_skills -v`

Expected: FAIL because the skills and validator do not exist.

- [ ] **Step 3: Implement frontmatter/contract validation**

Use a small YAML-frontmatter parser supporting the required scalar fields and `metadata` map. Enforce lowercase hyphen names, maximum lengths, `name == parent directory`, required headings, manifest stage/output consistency, and no skill declaring an artifact type outside the protocol.

- [ ] **Step 4: Write the ten skills and registry**

Keep each main file under 500 lines. Include exact commands (`coherence status`, `coherence route`, `coherence write`, `coherence validate`) and procedures for stale, blocked, conflicting, and partial artifacts. `audit-coherence` must include unrepresented-state and no-orphan-transition reasoning; `analyze-regression` must include conservative escalation; `revalidate-coherence` must require revision/evidence references.

- [ ] **Step 5: Run skill validation and full tests**

Run: `python -m unittest tests.test_skills -v`

Expected: PASS for the published tree and the intentionally malformed fixture.

Run: `python -m coherence validate-skills --json`

Expected: exit 0 and an empty error list.

- [ ] **Step 6: Commit the skills**

```text
git add skills src/coherence/cli.py src/coherence/workflow.py tests/test_skills.py
git commit -m "feat: publish composable coherence skills"
```

---

### Task 6: Add schemas, examples, evaluation suite, and dogfood generator

**Files:**
- Create: `examples/web-cache/app.py`
- Create: `examples/web-cache/README.md`
- Create: `examples/worker-service/worker.py`
- Create: `examples/worker-service/README.md`
- Create: `examples/clean-cli/ledger.py`
- Create: `examples/clean-cli/README.md`
- Create: `examples/scenarios.json`
- Create: `scripts/dogfood.py`
- Create: `tests/test_evaluations.py`
- Modify: `src/coherence/cli.py`
- Create: `src/coherence/evaluation.py`

**Interfaces:**
- `coherence eval` executes the deterministic fixture probes and reports pass/fail counts.
- Each scenario names its architecture, relevant capabilities, expected finding category, and negative-control expectation.
- `scripts/dogfood.py` builds a complete root `.coherence/` workspace from the framework's own files, leaving all handoffs independently readable.

- [ ] **Step 1: Write failing fixture and evaluation tests**

```python
def test_web_cache_delete_exposes_stale_derived_state():
    system = load_web_cache_fixture()
    system.create("a", "payload")
    system.delete("a")
    self.assertEqual(system.get("a"), "payload")

def test_worker_failure_leaves_partial_completion_state():
    worker = Worker()
    worker.process("job-1", fail_side_effect=True)
    self.assertEqual(worker.status("job-1"), "completed")
    self.assertNotIn("job-1", worker.outputs)

def test_clean_cli_preserves_state_across_rename():
    ledger = CleanLedger()
    ledger.rename("old", "new")
    self.assertEqual(ledger.lookup("new"), "present")
    self.assertIsNone(ledger.lookup("old"))
```

- [ ] **Step 2: Run fixture tests and verify the defect tests fail for the missing examples**

Run: `python -m unittest tests.test_evaluations -v`

Expected: FAIL because the fixture implementations are absent.

- [ ] **Step 3: Implement intentionally broken and clean fixtures**

Keep defects small and explicit: the web fixture must omit cache invalidation on delete; the worker must persist completion before its side effect; the clean CLI must perform an atomic in-memory rename. The tests must demonstrate actual behavior, not merely inspect source strings.

- [ ] **Step 4: Add evaluator and scenario metadata**

Run each probe, compare actual behavior to scenario expectations, and report a structured result with scenario ID, architecture, expected category, observed outcome, and evidence paths. Include a negative control that passes without a finding.

- [ ] **Step 5: Implement dogfood artifact generation**

Capture root evidence, create stable framework capabilities/contracts/transitions/traces/findings/plan/scope/validation entries, write them through the store, derive the ledger, and run `validate_all`. All generated artifacts must use current source revision and real evidence paths from the root repository.

- [ ] **Step 6: Run evaluation and dogfood tests**

Run: `python -m unittest tests.test_evaluations -v`

Expected: PASS, with two intentional defect detections and one clean negative control.

Run: `python scripts/dogfood.py`

Expected: exit 0, create the complete `.coherence/artifacts/` set, and print the ledger summary.

- [ ] **Step 7: Commit examples and dogfood evidence**

```text
git add examples scripts tests/test_evaluations.py src/coherence
git add .coherence
git commit -m "feat: add behavioral evaluations and self-audit evidence"
```

---

### Task 7: Write the GitHub-quality documentation and contributor workflow

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/methodology.md`
- Create: `docs/getting-started.md`
- Create: `docs/artifact-protocol.md`
- Create: `docs/extension-guide.md`
- Create: `docs/evaluation.md`
- Create: `CONTRIBUTING.md`
- Create: `LICENSE`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- README answers problem, differentiation, installation, invocation, artifacts, full workflow, incremental revalidation, evaluation evidence, limitations, and contribution path.
- Docs are authoritative and link to the actual skill/schema/CLI files without contradictory copies of the protocol.
- CI runs the same standard-library test command and validates skills.

- [ ] **Step 1: Add documentation checks to tests**

```python
def test_readme_contains_operational_quickstart():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in ("coherence init", "coherence route", ".coherence", "coherence invalidate"):
        self.assertIn(phrase, readme)
```

- [ ] **Step 2: Run the documentation test and verify its expected failure**

Run: `python -m unittest tests.test_documentation -v`

Expected: FAIL because release documentation is not present.

- [ ] **Step 3: Write the documentation and CI workflow**

Show one end-to-end handoff example, one stale-artifact repair example, a table of artifact contracts, a skill extension recipe, fixture evaluation interpretation, and explicit limitations. Keep claims tied to the included evaluations.

- [ ] **Step 4: Run documentation and full tests**

Run: `python -m unittest tests.test_documentation -v`

Expected: PASS.

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 5: Commit the public project surface**

```text
git add README.md docs CONTRIBUTING.md LICENSE .github
git commit -m "docs: prepare system coherence for release"
```

---

### Task 8: Perform full verification, self-audit repair, and release cleanup

**Files:**
- Modify any file identified by verification or dogfood findings.
- Test: all `tests/` files.
- Inspect: `.coherence/artifacts/`, `schemas/`, `skills/`, and git status.

**Interfaces:**
- `python -m unittest discover -s tests -v` is the authoritative test command.
- `python -m coherence validate --json` returns no errors for the root workspace.
- `python -m coherence validate-skills --json` returns no errors.
- `python -m coherence eval` reports two detected defects and one negative control.
- `python scripts/dogfood.py` is repeatable and leaves a current ledger.

- [ ] **Step 1: Run the complete verification commands from a clean install**

```text
python -m pip install -e .
python -m unittest discover -s tests -v
python -m coherence validate --json
python -m coherence validate-skills --json
python -m coherence eval
python scripts/dogfood.py
```

- [ ] **Step 2: Inspect outputs and repository state**

Check exit codes, test counts, validator error arrays, evaluation counts, dogfood ledger status, `git diff --check`, `git status --short`, and that no build/cache files are tracked. Confirm every capability/finding/action/validation reference resolves.

- [ ] **Step 3: Repair any finding with a new failing test first**

For each defect found by verification, add a focused regression test, run it to confirm the expected failure, apply the smallest fix, rerun the focused test, and then rerun the full suite. Do not weaken tests to match an implementation accident.

- [ ] **Step 4: Re-run dogfood and scoped invalidation**

Use an explicit changed path under `src/coherence/` and verify the regression scope maps to linked traces/contracts/capabilities. Use an unmapped path and verify conservative `scope-unknown` escalation. Re-run dogfood so the ledger records the latest source revision.

- [ ] **Step 5: Request an independent code review**

Provide the reviewer the final base and head SHAs, the spec, the plan, the test outputs, and the requirements checklist. Resolve all critical/important findings, then rerun the complete verification commands.

- [ ] **Step 6: Commit the release state**

```text
git add -A
git diff --cached --check
git commit -m "release: system coherence 0.1.0"
git status --short --branch
```
