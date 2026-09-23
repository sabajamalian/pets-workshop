# Artifacts and Test Reports

| [Previous: Rulesets and required workflows][walkthrough-previous] | [Next: Runners and hardware][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

The core workshop is complete. These advanced exercises extend the same shelter
application without requiring you to deploy anything to Azure.

## Scenario

A browser test failed overnight, but the volunteer investigating it cannot see what
the browser saw. The team also wants to pass a built frontend to another job without
building it again. We'll use artifacts for both tasks.

## Background

A cache helps restore dependencies on a later run. An **artifact** saves a specific
run's output, such as a build, report, or trace. Jobs do not share a filesystem;
uploading and downloading an artifact makes that handoff explicit.

The existing Playwright configuration writes an HTML report and records a trace on
the first retry. We'll retain these files even when a test fails. Separately, we'll
archive the Astro build, record its commit, and verify its SHA-256 checksums after
downloading it in another job.

> [!IMPORTANT]
> Checksums detect changed bytes, not a trustworthy producer. Someone who controls
> an artifact could change both the file and its checksum. Artifact attestations
> provide a separate provenance mechanism and are outside this exercise.

## Create the artifact workflow

1. Complete the [setup][setup] and [testing][testing] exercises. This lab uses the
   same Python and Node dependencies, but needs no Azure account or secrets.
2. Copy the [complete workflow][solution] into your repository:

    ```bash
    mkdir -p .github/workflows
    cp content/github-actions/solutions/10-artifacts/artifacts.yml .github/workflows/artifacts.yml
    ```

3. Read the three jobs before committing: `build-client` and `test-e2e` run in
   parallel; `verify` waits for `build-client`.
4. Commit and push to your workshop repository's default branch. Open **Actions**,
   choose **Artifacts and Reports**, and select **Run workflow**.

This is an opt-in manual lab. It does not replace the core **Run Tests** workflow
or create a second automatic deployment.

## Follow the build between jobs

The build step runs `npm ci` and `npm run build` in `app/client`. It then packages
only the build output and records the source commit:

```bash
mkdir -p "$RUNNER_TEMP/pets-build"
tar -czf "$RUNNER_TEMP/pets-build/site.tar.gz" -C app/client/dist .
cd "$RUNNER_TEMP/pets-build"
printf '%s\n' "$GITHUB_SHA" > commit.txt
sha256sum site.tar.gz commit.txt > SHA256SUMS
```

1. Expand the upload step. The display name includes the producer's run ID and
   attempt. The action also returns a unique artifact ID as a job output.
2. Open `verify`. It downloads that producer ID, checks the manifest, and compares
   `commit.txt` with the run's SHA. It does not execute the downloaded application.
3. Open the run's **Summary** and download the build artifact.

The upload uses `if-no-files-found: error` because a missing build must fail the
job. Retention is seven days; choose a period appropriate to your team's policy
and storage budget.

Consumers use `needs.build-client.outputs.artifact-id`, not a name reconstructed
from their own attempt number. Rerunning only a failed downstream job increments
its attempt without rerunning a successful build. The producer's output still
identifies the original artifact. `merge-multiple: true` extracts the selected ID
directly into `build/` rather than an artifact-named subdirectory.

> [!NOTE]
> Astro uses a Node server adapter here. This archive is a teaching build artifact,
> not a complete deployment image with runtime dependencies. The Azure workflow's
> `azd up` can rebuild the application. Do not describe that workflow as promoting
> this exact archive to production.

## Keep evidence from failed browser tests

1. Open the `test-e2e` job's last step. `if: ${{ !cancelled() }}` lets the diagnostic
   upload run after a failed test, without changing the test's failed result.
2. Download the `pets-browser-report-...` artifact from the run summary and extract
   it outside the repository.
3. In `app/client`, open the extracted report using:

    ```bash
    npx playwright show-report /absolute/path/to/extracted/playwright-report
    ```

4. Use the report's trace viewer for retried tests. No retry means there may be no
   trace; that is different from a missing HTML report.

Diagnostic uploads warn rather than fail when no files exist, since an earlier
dependency-install failure may prevent the browser from starting. Inspect the
original failure instead of treating a successful upload as a passing test suite.
Only report directories are uploaded, not databases, secrets, or `node_modules`.
Reports and traces can include page data and network responses. Use the workshop's
test data and review diagnostic contents before sharing them outside your team.

## Diagnose a broken handoff

1. On a practice branch, replace `artifact-ids` in `verify` with a nonexistent ID
   such as `'1'`.
2. Dispatch the workflow on that branch. Confirm that download fails rather than
   silently rebuilding.
3. Restore the producer output reference. To test integrity instead, insert `printf 'changed' >>
   site.tar.gz` immediately before `sha256sum --check SHA256SUMS` in `verify`.
4. Confirm checksum verification fails, remove the deliberate change, and rerun.
5. Separately make a temporary browser assertion fail. Confirm the test job stays
   failed and the diagnostic artifact is still available. Restore the assertion.
6. On a successful run, rerun only `verify`. Confirm it still downloads the
   successful build's artifact rather than inventing a new attempt's name.

## Summary and next steps

You can now keep browser evidence and pass a specific build between isolated jobs.
Next, we'll run the API tests on [different runner platforms][walkthrough-next].

## Resources

- [Storing and sharing workflow data][artifacts]
- [Playwright reports and traces][playwright]
- [Artifact attestations][attestations]
- [Workshop troubleshooting][troubleshooting]

| [Previous: Rulesets and required workflows][walkthrough-previous] | [Next: Runners and hardware][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[walkthrough-previous]: 9-required-workflows.md
[walkthrough-next]: 11-runners-and-hardware.md
[setup]: 0-setup.md
[testing]: 3-running-tests.md
[solution]: solutions/10-artifacts/artifacts.yml
[troubleshooting]: troubleshooting.md
[artifacts]: https://docs.github.com/actions/using-workflows/storing-workflow-data-as-artifacts
[playwright]: https://playwright.dev/docs/trace-viewer
[attestations]: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
