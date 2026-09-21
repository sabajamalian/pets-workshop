# Capstone: From Pull Request to Approved Deployment

| [Previous: Agentic workflows][walkthrough-previous] | [Next: Workshop overview][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

## Scenario

The shelter now has tests, reusable automation, and clearer trust boundaries. Let's
combine them into one workflow that checks a pull request, verifies its build, and
checks the merged commit again. An owner can then choose an approved Azure deployment.

AI analysis stays in its separate manual workflows. A model cannot merge code,
approve an environment, or deploy the application in this exercise.

## Background

The capstone runs the real Python unit tests, Chromium end-to-end tests, and Astro
build. A fourth job verifies the uploaded build. One stable required check,
`capstone-passed`, fails unless all four results succeed.

| Event | Behavior |
| --- | --- |
| Pull request to `main` | Validate and verify artifacts with read-only permissions; no deployment. |
| Push to `main` | Validate the merged commit and recheck its artifact in `post-merge`; no automatic deployment. |
| Manual run with `deploy=false` | Validate and verify only. This is the default. |
| Manual run on `main` with `deploy=true` | Validate first, then request `pets-production` approval for Azure deployment of that run's commit. |

Artifact display names include the producer's run ID and attempt. Consumers use
the uploaded artifact ID exposed by the build job, including when only downstream
jobs are rerun. They download the same artifact rather than rebuild it. The optional Azure job separately uses `azd up`
from the exact validated commit; it may rebuild and does not deploy the uploaded
archive unchanged.

## Prepare the companion files

1. Complete the core lessons and advanced [artifact][artifacts] and
   [environment][environments] exercises.
2. Keep `.github/actions/setup-python-env/action.yml` from [custom actions][custom].
   The capstone's API matrix calls that action.
3. Keep `.github/workflows/reusable-deploy.yml` from [reusable workflows][reuse].
   GitHub must be able to resolve this local workflow even when deployment is
   skipped. It requires the `deploy-ref` and optional `environment-name` inputs.
4. Copy the [complete capstone][solution]:

    ```bash
    cp content/github-actions/solutions/15-capstone/capstone.yml .github/workflows/capstone.yml
    ```

5. Review each trigger, job dependency, permission, and deployment condition before
   committing.

> [!IMPORTANT]
> Installing this workflow does not disable earlier workflows. If you enabled
> **Deploy App** in the core track, it can still deploy after **Run Tests** passes,
> independently of this capstone. For this lab's manual-only deployment model, have
> an owner disable that automatic deploy workflow in the Actions UI before testing.
> Do not assume `deploy=false` controls other workflows.

## Run and require the checks

1. Push a practice branch and open a pull request.
2. Observe the API version matrix, browser tests, frontend build, and artifact
   verification. The shared action installs the API dependencies; the unit tests
   use an in-memory database and Playwright seeds its own separate test database.
3. Confirm `capstone-passed` is green only after every required result succeeds.
4. Add `capstone-passed` to the default-branch ruleset alongside the core
   `tests-passed` check. Keep both workflows while both are required.
5. After review and merge, inspect the `push` run and its post-merge summary.

Do not add environment approval to a job required for ordinary fork PR validation.
The unprotected `verify` job establishes the artifact check before any release
approval is requested.

## Exercise the failure paths

1. Temporarily break one API assertion on a practice branch. Confirm both the test
   and aggregate gate fail.
2. Restore it, then set a nonexistent artifact ID in `verify`. Confirm a missing artifact
   blocks the gate even when the tests and build pass.
3. Restore the producer ID reference and modify the downloaded archive before checksum verification.
   Confirm the gate also rejects changed bytes.
4. Restore the intended workflow, run it again, and inspect the saved browser
   diagnostics. Report uploads must not hide test failures.

`if: always()` makes the aggregate job evaluate dependency results even after a
failure. It explicitly requires `success`; skipped or cancelled dependencies do
not accidentally satisfy the gate.

## Optional: request an Azure deployment

1. Finish the owner-only environment and Azure federated-credential setup in
   [Protected environments][environments]. Keep the `pets-production` branch
   restriction, required reviewers, and prevention of self-review.
2. Run **Pets Capstone** manually on `main` with `deploy=false`. Confirm the
   deployment job is skipped.
3. Only on an approved disposable Azure environment, dispatch again with
   `deploy=true`. This may provision resources and incur charges.
4. Confirm validation passes before the reusable deployment job waits for approval.
5. Have another configured reviewer inspect the commit and results, then approve.
6. Verify the deployed shelter endpoint using the Azure lesson's instructions.
   Review resource cleanup with the owner afterward.

A branch restriction controls the workflow ref. This capstone also passes
`github.sha` from the manual run, rather than a user-controlled arbitrary ref, to
the deployment workflow. The core manual rollback workflow remains a separate
trusted-operator capability.

## Summary and next steps

You've assembled a pipeline with real application checks, a stable merge gate,
build handoff, diagnostic retention, and an explicit deployment approval boundary.
Return to the [workshop overview][walkthrough-next] for the full lesson map.

Further exercises could add immutable image promotion, staging, artifact
attestations, or a bounded draft-PR agent. Those require additional design and are
not implemented by this capstone.

## Resources

- [Complete solutions and local validation][solutions]
- [Troubleshooting][troubleshooting]
- [GitHub Actions documentation][actions]

| [Previous: Agentic workflows][walkthrough-previous] | [Next: Workshop overview][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[walkthrough-previous]: 14-agentic-workflows.md
[walkthrough-next]: README.md
[artifacts]: 10-artifacts-and-reports.md
[environments]: 12-protected-environments.md
[custom]: 7-custom-actions.md
[reuse]: 8-reusable-workflows.md
[solution]: solutions/15-capstone/capstone.yml
[solutions]: solutions/README.md
[troubleshooting]: troubleshooting.md
[actions]: https://docs.github.com/actions
