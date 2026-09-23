# Troubleshooting GitHub Actions

Use this reference alongside the [workshop lessons][overview]. Start with the first
failed step, not the final gate: the gate summarizes earlier results.

## Reproduce the command

1. Note the workflow's source commit, working directory, runtime version, event,
   and first nonzero exit code.
2. Run the same command locally with the same dependencies. Use Python 3.13 and a
   supported Node 22 release (22.12.0 or newer) for the workshop defaults.
3. For API tests, use `DATABASE_PATH=:memory:` and `PYTHONDONTWRITEBYTECODE=1` so
   importing Flask does not change the checked-in shelter database.
4. For browser failures, download the [Playwright artifact][artifacts] rather than
   guessing from the final assertion alone. A failed run can still have a useful
   report and trace.

## Common failures

| Symptom | What to inspect | What to do |
| --- | --- | --- |
| No **Run workflow** button | File location, default-branch registration, `workflow_dispatch` | Install the solution at its documented destination and merge the workflow to the default branch before selecting another ref. |
| Invalid YAML or expression | The annotation's line and column | Check indentation, `run` versus `runs-on`, and which contexts are allowed at that location. Validate the complete file, not a partial snippet. |
| `npm ci` fails | Node version and manifest/lockfile agreement | Reproduce with the supported runtime. Repair the lockfile using npm and review it; do not replace `npm ci` with an unreviewed dependency update in CI. |
| Local action not found | Checkout order and copy destination | Check out first and install `action.yml` under `.github/actions/setup-python-env/`, not `.github/workflows/`. |
| Python imports fail | Selected interpreter and installed server requirements | Use the setup-python interpreter and `python -m pip`; do not mix system Python and a different virtual environment. |
| API test modifies a database | `DATABASE_PATH` at import time | Use an in-memory or dedicated temporary test database, never the tracked shelter database. |
| Browser cannot reach the API | Playwright web-server logs, interpreter, port 5100 | Check server startup and dependencies. Stop only the stale process you own; do not bypass the test with a mocked production result. |
| No browser trace | Retry count and test result | A trace is recorded on the first retry, not on every passing test. Inspect the HTML report and startup logs too. |
| Artifact not found | Producer result, artifact ID, and retention | Use the ID returned by the producer, including after downstream-only reruns; do not reconstruct a name from the consumer's attempt or silently rebuild. |
| Checksum mismatch | The transferred archive and manifest | Fail the gate, investigate, and rebuild from reviewed source. Do not rewrite the checksum in the verification job. |
| Required check remains expected | Exact job/check name and trigger filters | Require the stable aggregate check. Skipping an entire required workflow with a path filter can leave it pending. |
| Gate skipped or unexpectedly green | `if: always()`, `needs`, explicit result checks | Require every intended dependency to report `success`; failure, cancellation, and skipping are not success. |
| Runner stays queued | All requested labels, group access, runner status | Correct routing or access, or cancel the run. More CPU does not fix a label that has no matching runner. |
| Azure deploy is skipped | Upstream event, branch, repository, conclusion | The automatic path accepts only successful trusted `main` push CI. PR CI must not trigger a privileged deploy. |
| Azure deploy checks out the wrong commit | `workflow_run.head_sha` and reusable `deploy-ref` | Carry the successful CI run's SHA explicitly; the deployment workflow's own `github.sha` can be different. |
| Azure login fails after adding an environment | OIDC subject, audience, issuer, and role assignment | Match the environment-scoped identity described in the [environment lesson][environments]. Do not add a long-lived secret as a workaround. |
| Approval never requested | Environment name and protection configuration | Create and protect the environment before running the workflow. Referencing an unconfigured name is not an approval rule. |
| Cannot approve your own run | Prevent self-review and reviewer eligibility | Have a different configured reviewer approve it. Keep the protection enabled. |
| Copilot CLI denies access or a flag | Entitlement, organization policy, pinned version and current reference | Fail closed, have the owner review the setup, and keep using the credential-free path. Never retry by dropping tool restrictions. |
| `gh aw compile` rejects a field | `gh aw version`, error location, and lesson 14's pinned compiler | Use v0.88.8 for the snapshot or review a deliberate upgrade. Preview docs can describe fields newer than an installed compiler. |
| Agentic source changed but behavior didn't | Markdown and `.lock.yml` at the run's SHA | Recompile and commit both. Actions executes the generated YAML, not Markdown alone; run the [freshness check][validation]. |
| Agent fails authentication after approval | `COPILOT_GITHUB_TOKEN` repository secret, Copilot access and billing policy | Follow [lesson 14][agentic]. The activation environment doesn't make its secrets available to every generated job. Personal forks cannot assume organization-token billing. |
| Agentic workflow finishes but no issue appears | `safe-outputs.staged` and the safe-output job summary | Staged mode intentionally previews the issue. It still runs AI. Do not disable staged mode just to make an issue appear. |
| Agent can't read a file or detection fails | Repository allowlist, approved-integrity policy, exact commit, tool logs, detection output | Inspect the denial or missing evidence. Do not add shell access, broad tokens, or disable detection to force success. |
| Agent hits a time, turn, or credit limit | Agent and detection logs, separate credit limits, Actions usage | Stop and review the task and budget with the owner. Re-running consumes usage again. |
| Azure YAML fails actionlint | Which migration file was selected | `azure-pipelines.yml` is Azure syntax, not Actions YAML. Validate the [migration source and target][migration] with their respective tools. |
| Importer leaves a task untranslated | Audit/dry-run report, extension version, custom tasks and templates | Manually map the behavior and test it. An output YAML file is not proof of migration parity. |
| Migrated CI differs or remains queued | Source SHA, triggers/branch policy, runtime, working directory, pool/runner access | Compare the same commit and commands. Reconfigure identities and approvals explicitly; never copy a service-connection secret into the workflow. |

## Temporary debug logging

An owner can enable `ACTIONS_RUNNER_DEBUG` and `ACTIONS_STEP_DEBUG` as repository
variables or secrets set to `true`, then rerun the failing job. Remove those settings
when finished. Debug logs can expose additional context; don't print credentials
or upload the entire runner workspace.

## Keep deliberate failures contained

Use practice branches for break/fix exercises, and restore the intended behavior
before merging. Never weaken permissions, switch to `pull_request_target`, remove
environment approval, or disable a failing check just to make a run green.

Local checks cannot prove that a reviewer, Azure trust relationship, hosted runner
pool, or Copilot entitlement is configured. Treat those as owner-operated checks,
not as results inferred from valid YAML.

## Resources

- [Return to the workshop][overview]
- [Complete opt-in solutions][solutions]
- [Enabling diagnostic logging][debug]

[overview]: README.md
[artifacts]: 10-artifacts-and-reports.md
[environments]: 12-protected-environments.md
[solutions]: solutions/README.md
[validation]: solutions/README.md#maintaining-the-examples
[agentic]: 14-agentic-workflows.md
[migration]: 16-migrating-azure-pipelines.md
[debug]: https://docs.github.com/actions/monitoring-and-troubleshooting-workflows/enabling-debug-logging
