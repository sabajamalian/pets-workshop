# Simulating an Agentic Workflow with Pets API Tests

| [Previous: Copilot CLI][walkthrough-previous] | [Next: Capstone][walkthrough-next] |
|:--------------------------------------------|----------------------------------:|

## Scenario

The shelter wants a repeatable way to evaluate proposed automation before giving
it permission to change anything. A volunteer submits a short goal, such as
"Explain how dog-list tests work." The system records that goal, runs a fixed
Pets API test action, validates the evidence, and asks a human to approve the
final audit.

This is a **deterministic simulation, not a real AI agent**. No CLI, model,
provider, or AI credential is involved. The goal is inert data. It never selects
a command, test, filename, dependency, prompt, or approval decision.

## Background

An agentic system can plan actions toward a goal, choose tools, observe results,
and decide whether to iterate. Those choices add uncertainty. This lab retains
the lifecycle but replaces its planner with a fixed plan and its tool selection
with a single allowlisted action.

| Lifecycle stage | This exercise |
|-----------------|---------------|
| Intake and trust classification | Manual input, validated to 1 to 200 characters, never trusted as instructions |
| Context | An explicit list of Flask source, model, and unit-test files |
| Plan | A fixed JSON plan with one iteration and a 90-second test budget |
| Policy check | Default-branch-only dispatch, no write permissions or secrets |
| Act | Run the existing `test_app` suite once with Python 3.13 |
| Observe | Capture unittest output and structured results |
| Validate | Require successful, nonempty tests and a clean checkout, including ignored files |
| Iterate or stop | No automatic retry or repair; failed validation stops the run |
| Human approval and audit | An independent reviewer approves `pets-agentic`, then trusted code validates the downloaded evidence |

The real Pets suite uses Flask's test client and mocks database queries. It
does not need a listening server, frontend build, browser, seeded shelter
database, or Node.js. Importing Flask models still creates tables, so every
test process sets `DATABASE_PATH=:memory:`. `PYTHONDONTWRITEBYTECODE=1` and
Python's `-B` keep bytecode out of the context.

The no-write contract means **no changes inside the checkout**, not that the
runner disk is immutable. Dependencies, a virtual environment, copied source,
test logs, and audit data all live outside the checkout under `RUNNER_TEMP`.
GitHub-hosted job isolation and least-privilege credentials reduce exposure;
this example is not a sandbox for running hostile Python or compromised
dependencies. The workflow, tests, helper, and dependencies must be trusted.

## 1. Review and install the complete example

1. Review [`agentic-safe.yml`][solution-workflow] and
   [`lifecycle.py`][solution-helper]. Keep the helper at
   `content/github-actions/solutions/14-agentic-workflows/lifecycle.py`.
2. Copy only the workflow to `.github/workflows/agentic-safe.yml` in your
   workshop repository. `test_lifecycle.py` is an optional local regression
   companion, not a workflow step.
3. Have the workflow, helper, and test action reviewed before installing them
   on the default branch. The example never fetches code from the goal input.

The form input enters the process environment, not interpolated shell code:

```yaml
- name: Intake, plan, act, observe, and validate once
  env:
    UNTRUSTED_GOAL: ${{ inputs.goal }}
    DATABASE_PATH: ':memory:'
    PYTHONDONTWRITEBYTECODE: '1'
  shell: bash
  run: |
    set -euo pipefail
    python -B content/github-actions/solutions/14-agentic-workflows/lifecycle.py simulate \
      --checkout "$GITHUB_WORKSPACE" --work-dir "$RUNNER_TEMP/pets-agentic" \
      --python "$RUNNER_TEMP/pets-api-venv/bin/python"
```

The complete workflow creates that virtual environment and installs
`app/server/requirements.txt` outside the checkout first. It does not cache or
upload dependencies. The helper copies only:

```text
app/server/app.py
app/server/test_app.py
app/server/models/__init__.py
app/server/models/base.py
app/server/models/breed.py
app/server/models/dog.py
```

There is no database or CSV seed data in the copied context. The test subprocess
loads `test_app` with unittest, using the same test suite as
`python -m unittest test_app -v`. It writes a structured result in addition to
the normal output so validation need not parse a human-oriented summary.

## 2. Configure the protected audit environment

An owner or administrator must do this before the first hosted demonstration:

1. Create **`pets-agentic`** under **Settings > Environments**.
2. Add **Required reviewers**, enable **Prevent self-review**, and disable
   administrator bypass where available. Arrange a reviewer other than the
   person dispatching the workflow. One configured reviewer's approval is
   enough for GitHub to release the job.
3. Under **Deployment branches and tags**, select **Selected branches and
   tags** and add only a **Branch** rule for the exact default branch. Do not
   use unrestricted branches or a tag rule with the same name.
4. Leave environment secrets empty. This job only verifies audit data.
5. Verify [plan and repository visibility support][environment-rules]. Public
   repositories can use these review gates on Free, Pro, or Team. Although
   Pro and Team support private environments, required reviewers on those
   plans are public-repository-only. Confirm applicable Enterprise support
   for private/internal repository review gates.

> [!IMPORTANT]
> A workflow reference can create an unprotected environment automatically.
> Confirm the environment exists with these protections before dispatching.
> If the required features or a second reviewer are unavailable, run the local
> simulation and discuss the approval stage. Do not delete the gate or call
> the walkthrough equivalent to enforced human approval.

The environment label makes GitHub track an environment job. It does not mean
this lab deploys the application or needs Azure. No repository branch, issue,
PR, release, or external resource is created.

## 3. Observe the hosted lifecycle

1. In **Actions**, choose **Pets agentic simulation**, select the default
   branch, and submit a short non-sensitive goal.
2. Watch `simulate`. Its job is bounded to eight minutes, including dependency
   installation. The test action has a separate 90-second limit and one
   iteration. Test output is capped at 128 KiB.
3. Download `pets-agentic-audit-<run-id>-<attempt>`. It contains exactly:

   | File | Purpose |
   |------|---------|
   | `plan.json` | JSON-escaped goal, source SHA, context allowlist, fixed action and budget |
   | `observation.txt` | Bounded unittest output |
   | `result.json` | Counts and success value from `unittest.TestResult` |
   | `verdict.json` | Test exit status, clean-checkout result, and acceptance decision |
   | `manifest.json` | SHA-256 checksums of the other four files |

4. Check that the suite ran at least one test, with zero failures, errors,
   skipped tests, expected failures, or unexpected successes. The gate does
   **not** require a particular test count and does not trust the word `OK`
   appearing in a log.
5. Confirm `checkout_clean` and `accepted` are true in `verdict.json`.
6. Have the independent reviewer inspect the evidence and approve the waiting
   `human-audit` job. It downloads the producer's exact artifact ID from the same run,
   checks its exact file set, sizes, checksums, result fields, and expected
   source SHA, then writes a fixed summary.

Expected outcome: successful tests, a narrow audit artifact retained for seven
days, a visible approval wait, and a final read-only summary. The audit job
executes the helper from the reviewed checkout, **never Python from an artifact**.

The artifact manifest catches missing or changed bytes. Anyone who can replace
both the data and its manifest can replace their checksums. This is consistency
checking, not an attestation, proof of origin, or cryptographic provenance.
The trusted run, reviewed workflow, and independent reviewer remain essential.
The upload step exposes its `artifact-id` as a `simulate` job output. The audit
job requires a nonempty numeric ID, then supplies it to `artifact-ids` with
`merge-multiple: true` so the five files land directly in the audit directory.
It never reconstructs an artifact name from the consumer's `github.run_attempt`.
Rerunning only the audit job therefore reuses the successful producer's exact
artifact, even when the consumer has a newer attempt number. If that artifact
expired or was deleted, verification fails; start a new full workflow run.

## 4. Verify failure propagation and the no-write boundary

The helper captures output without `tee`, evaluates the subprocess return code,
and returns a nonzero result if tests fail, time out, or violate validation.
Artifact upload uses `if: always()` for diagnostics, but there is no
`continue-on-error`. Uploading a log does not turn a failed action into success.
Missing artifacts also fail. Cancellation or a runner crash may prevent complete
diagnostics, but cannot release the approval-dependent job.

Before and after the action, the helper applies this checkout check:

```bash
git status --porcelain=v1 --untracked-files=all --ignored
```

Any output is rejection, including tracked/staged edits, new files, databases,
`__pycache__`, and ignored dependency directories. It is not enough to run
`git diff`, which misses untracked and ignored files. Local environments with
an existing ignored `.venv` are deliberately not accepted as clean checkouts.

The final job requires exactly a successful dependency:

```yaml
needs: simulate
if: >-
  needs.simulate.result == 'success' &&
  github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
environment: pets-agentic
```

| `simulate` result | Final audit eligible? |
|-------------------|-----------------------|
| `success` on default branch | Yes, but still needs environment approval |
| `failure`, `cancelled`, or `skipped` | No |
| Any result on another branch or a tag | No |

## 5. Break, diagnose, and fix offline

Use Python 3.13 with the dependencies from `app/server/requirements.txt` already
installed. Dependency installation may need network access; the regression
commands below do not. Use an existing virtual environment if available:

Run these local helpers on Linux, macOS, or WSL. Their output limit uses
Python's `resource` module and `RLIMIT_FSIZE`, which native Windows does not
provide. The hosted jobs use `ubuntu-latest`.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover \
  -s content/github-actions/solutions/14-agentic-workflows -p 'test_*.py' -v
```

Or replace `.venv/bin/python` with the path to a prepared Python 3.13 environment.
The [regression tests][solution-tests] create local Git clones of the committed
repository under this stage's `.validation` directory, then remove them. They
never commit, push, contact a model, or modify the original checkout. Their
isolated checkout lets them reject *all* ignored paths without deleting your
normal development environment.

Try these controlled failures by inspecting or adapting the local fixtures:

1. **Fail a test:** `test_failing_api_assertion_keeps_nonzero_exit_and_log`
   appends a deliberate failing assertion to the copied test file outside the
   checkout. Expect a nonzero simulation result and a retained failure log.
   Fix the assertion, not the exit-status handling.
2. **Unexpected file:** `test_post_action_ignored_write_rejected` creates an
   ignored `node_modules/unexpected.txt` inside the fixture checkout after the
   action. Tests pass, but the no-write check rejects it. Remove the fixture
   write or move legitimate output outside the checkout, not into an ignore
   rule.
3. **Inert goal:** `test_goal_is_inert` records shell substitutions, semicolons,
   a newline, and Actions-like expression text. Check JSON escaping and confirm
   the sentinel file was never created. Never add `eval`, `shell=True`, or a
   generated shell script.
4. **Oversized goal:** 201 characters must fail before tests start. A blank goal
   also fails. A 200-character nonempty goal fits the contract.
5. **Audit damage:** Modify `observation.txt`, remove `result.json`, add an
   unexpected file, or replace a result with a symlink in a downloaded fixture.
   Every case must fail audit verification. A different source SHA must fail too.

For a standalone local run after dependencies are prepared:

```bash
stage=content/github-actions/solutions/14-agentic-workflows
scratch="$PWD/$stage/.local-check"
mkdir "$scratch"
git clone --quiet --shared --no-hardlinks . "$scratch/checkout"
UNTRUSTED_GOAL='Explain the shelter dog-list test strategy' \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$stage/lifecycle.py" simulate \
  --checkout "$scratch/checkout" --work-dir "$scratch/run" \
  --python "$PWD/.venv/bin/python"
python3.13 -B "$stage/lifecycle.py" audit \
  --directory "$scratch/run/audit" \
  --expected-sha "$(git -C "$scratch/checkout" rev-parse HEAD)"
```

The snapshot contains the last committed API, not uncommitted API edits. A run
directory must be new; inspect and remove only your `.local-check` fixture
after the exercise, or choose a new fixture name. Do not run cleanup against
the repository checkout or a shared runner directory.

## Summary and next steps

You exercised intake, a deterministic plan, bounded action, observation,
independent validation, stopping, and human approval without a model. Runtime
limits constrain this simulation; they are not general AI spending caps.

A real planner, autonomous code editing, draft-PR creation, issue/comment
triggers, publishing privileges, model retries, attestations, and deployment
are outside this lab. If exploring real automation later, review the maintained
[GitHub Agentic Workflows tooling][gh-aw] and its current permissions, generated
workflow, isolation, and output controls. This example is ordinary Actions
YAML, not an implementation using that tool.

Continue to the [capstone][walkthrough-next] to combine the shelter's real
validation and human-controlled deployment path. Keep AI out of automatic PR
checks and deployment approval.

## Resources

- [Complete simulation workflow][solution-workflow]
- [Deterministic lifecycle helper][solution-helper]
- [Offline regression tests][solution-tests]
- [The Pets API unit tests][pets-tests]
- [Python unittest result API][unittest-results]
- [Workflow-dispatch event][workflow-dispatch]
- [Environment protection and availability][environment-rules]
- [GitHub Agentic Workflows][gh-aw]
- [Source workshop lifecycle exercise][source-lesson], adapted for the Pets API

| [Previous: Copilot CLI][walkthrough-previous] | [Next: Capstone][walkthrough-next] |
|:--------------------------------------------|----------------------------------:|

[walkthrough-previous]: 13-copilot-cli.md
[walkthrough-next]: 15-capstone.md
[solution-workflow]: solutions/14-agentic-workflows/agentic-safe.yml
[solution-helper]: solutions/14-agentic-workflows/lifecycle.py
[solution-tests]: solutions/14-agentic-workflows/test_lifecycle.py
[pets-tests]: ../../app/server/test_app.py
[unittest-results]: https://docs.python.org/3/library/unittest.html#unittest.TestResult
[workflow-dispatch]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
[environment-rules]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
[gh-aw]: https://github.github.com/gh-aw/
[source-lesson]: https://github.com/sabajamalian/workshop-github-action/tree/main/workshop/06-agentic-workflows
