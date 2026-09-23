# Optional: Migrating Azure Pipelines to GitHub Actions

| [Previous: Capstone][walkthrough-previous] | [Next: Workshop overview][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

## Scenario

The shelter already runs its Pets checks in Azure DevOps. Its volunteers want those
checks beside their GitHub pull requests, but don't want a migration to silently
drop a browser test, lose a failed run's report, or deploy twice.

We'll translate a small Azure pipeline into GitHub Actions, compare the behavior,
and plan a read-only CI cutover. No Azure deployment, AI service, or application
secret is part of this exercise.

## Background

This is an optional extension, not a prerequisite for the earlier lessons.
The main lab needs only your workshop repository and GitHub Actions. You can read
the Azure source side by side without an Azure DevOps account. Running that source
and using GitHub Actions Importer are separate, optional exercises for an authorized
owner with an existing Azure DevOps Services project.

Both [the Azure source][source] and [the reviewed GitHub translation][solution] live
under `solutions/16-migration/`. Neither is active there. The source has
`trigger: none` and `pr: none`; the translation has only `workflow_dispatch`.
Copy only the translation into `.github/workflows`. Azure pipeline YAML is not
GitHub Actions YAML.

The pipeline checks the real Flask API and Astro client:

| Azure job in stage `Validate` | GitHub job | Contract |
| --- | --- | --- |
| `TestApi` | `test-api` | Python 3.13, server requirements, `python -m unittest test_app -v` in `app/server`, `DATABASE_PATH=:memory:`, and `PYTHONDONTWRITEBYTECODE=1`. |
| `TestE2E` | `test-e2e` | Python 3.13 for Flask, Node 22, `npm ci`, Chromium installation, and `npm run test:e2e -- --project=chromium` in `app/client`; preserve browser diagnostics after failure. |
| `BuildClient` | `build-client` | Node 22, `npm ci`, and `npm run build` in `app/client`; publish `site.tar.gz`, `commit.txt`, and `SHA256SUMS`. |
| `Verify` | `verify` | Wait for the build, download its artifact, verify checksums, and compare the recorded commit with this run. |
| `MigrationPassed` | `migration-passed` | Evaluate all four results, even after failure; require every result to be successful. |

The first three jobs may run in parallel, subject to agent capacity. `Verify`
depends only on `BuildClient`. The aggregate gate depends on all four jobs.
The single Azure stage becomes a dependency graph in one GitHub workflow; there's
no GitHub `stages:` key to copy. More complex stage boundaries need explicit design,
not a mechanical rename.

## Inventory before translating

1. Open the two solution files side by side. Identify each tool installation,
   working directory, environment variable, job dependency, and uploaded path.
2. List the controls that live outside an existing Azure YAML file: pipeline UI
   trigger overrides, schedules, branch policies, variable groups, service
   connections, agent access, environments, and approvals.
3. Mark each item as preserved, deliberately changed, or requiring an owner's
   manual setup. Do not treat a converter's successful exit as this inventory.
4. Keep dependencies and test commands unchanged while checking parity. Add caches
   or faster runners later so performance changes don't obscure migration defects.

Use this translation guide while reading:

| Azure Pipelines | GitHub Actions | Review point |
| --- | --- | --- |
| `checkout: self` | `actions/checkout` | GitHub requires an explicit checkout. Both examples avoid leaving checkout credentials behind. |
| `UsePythonVersion@0`, `versionSpec: '3.13'` | `actions/setup-python`, `python-version: '3.13'` | Install Python for both the unit-test job and Playwright's Flask server. |
| `UseNode@1`, `version: '22.x'` | `actions/setup-node`, `node-version: '22'` | Both select Node 22. Older pipelines may use `NodeTool@0` and its different `versionSpec` input. |
| `bash`, `workingDirectory` | `run`, `shell: bash`, `working-directory` | Preserve quoting and exit codes. Azure scripts use `set -euo pipefail`; explicit GitHub Bash uses fail-fast and pipefail behavior. |
| `dependsOn`, `condition` | `needs`, `if` | Translate the dependency graph and failed/skipped/cancelled behavior, not just the happy path. |
| `PublishPipelineArtifact@1`, `DownloadPipelineArtifact@2` | `actions/upload-artifact`, `actions/download-artifact` | Preserve paths, missing-file behavior, producer identity, and retention policy. A cache is not an artifact. |
| `pool`, `vmImage`, demands | `runs-on`, runner labels and groups | Similar image labels don't guarantee identical tools, network access, capacity, or isolation. |
| Step/job/stage templates and parameters | Composite actions, reusable workflows, and inputs | There is no direct translation of Azure's template expansion language. Use a composite for shared steps and a reusable workflow for jobs. |

All GitHub actions in the solution are pinned to reviewed full commit SHAs. Task
major versions such as `UseNode@1` are not equivalent to an immutable action pin.

### Translate variables and expressions deliberately

- Azure `$(name)` is a macro expanded by the pipeline; `$NAME` in Bash is a shell
  environment variable. Do not blindly replace every `$()` string: `$(cat
  commit.txt)` in both examples is shell command substitution.
- Azure `${{ }}` template expressions are evaluated when the pipeline is compiled.
  `$[ ]` runtime expressions and `condition: eq(...)` have different evaluation
  rules. GitHub `${{ }}` uses contexts such as `github`, `env`, `vars`, `inputs`,
  `steps`, and `needs`; matching delimiters don't imply matching semantics.
- Move nonsecret configuration to scoped `env` or configuration `vars`. Variable
  groups, their permissions, secret values, and Key Vault links don't become GitHub
  configuration automatically. Recreate only required settings with an owner, at
  repository, organization, or environment scope. Neither solution needs secrets.
- Azure's named step uses `##vso[task.setvariable ...;isOutput=true]`; its consumer
  reads `dependencies.BuildClient.outputs['package.artifactName']`. In GitHub,
  an action's output or a value written to `$GITHUB_OUTPUT` must be exposed as a
  job output before another job can read `needs.build-client.outputs...`.

## Install and run the manual translation

1. Complete [setup][setup] and [running tests][testing]. No earlier custom action
   or reusable deployment workflow is required for this self-contained example.
2. Copy only the reviewed GitHub workflow:

    ```bash
    mkdir -p .github/workflows
    cp content/github-actions/solutions/16-migration/migrated-ci.yml .github/workflows/migrated-ci.yml
    ```

3. Check its manual trigger, `contents: read`, checkout
   `persist-credentials: false`, finite job timeouts, and absence of deployment
   steps. Commit and push it to your workshop repository's default branch.
4. Open **Actions > Migrated Pets CI > Run workflow**. Select the intended branch.
   A manually dispatched workflow must exist on the default branch to be available
   in the UI.
5. Record the run's full commit SHA. Confirm all five jobs complete successfully,
   and download the build and browser artifacts from the run summary.

This workflow doesn't provision anything, but hosted runner minutes and artifact
storage are subject to your account's limits and billing. Installing it also does
not disable earlier workflows. If earlier exercises enabled automatic Azure
deployment, have the owner disable those deploy workflows before pushing lab
changes. The migration workflow's read-only permissions don't control another
workflow's credentials or triggers.

### Expected behavior

The unit tests use an in-memory database; Playwright seeds its own test database
and starts Flask and Astro through the existing Playwright configuration. Both
pipelines set `CI=true` so worker count, retries, and server reuse match. Chromium
is installed with Linux dependencies before testing.

The build artifact contains only the Astro output archive and two verification
files, not source, databases, or `node_modules`. The consumer verifies it without
executing the downloaded app. Astro's Node adapter still needs runtime dependencies
for a real deployment, so this archive is a teaching artifact, not a complete
production deployment image. Checksums detect changed bytes, not a trusted
producer's identity.

The diagnostic artifact contains `playwright-report/` and, when produced,
`test-results/`. HTML reports are retained even when an assertion fails; traces
appear on the first retry. If dependency installation fails before any report
exists, both examples warn about absent diagnostics without masking the original
failure. They do not publish JUnit results to Azure's **Tests** tab.

GitHub retains both artifacts for seven days. Azure Pipeline Artifacts follow the
run's retention policy, not an equivalent per-task `retention-days` input. Record
that difference and have the owner review the project's retention settings.
Reports can contain page data and network responses; use workshop test data and
review contents before sharing them.

### Follow the producer, not the consumer's attempt

1. In Azure, find the `package` step's `artifactName` output and the
   `PublishPipelineArtifact@1` task that publishes that exact name.
2. Follow it into `Verify`. `DownloadPipelineArtifact@2` uses `buildType: current`
   and the producer's output, not another pipeline's latest successful run.
3. In GitHub, find `steps.upload.outputs.artifact-id`, the build job's output, and
   `verify`'s `artifact-ids` input. `merge-multiple: true` extracts the selected
   artifact directly into `build/`.

Display names include producer run/attempt identifiers to avoid collisions. Azure
includes both stage and job attempts. GitHub consumers use the artifact **ID**:
rerunning only a failed downstream job increments the run attempt without
rebuilding a successful producer. Constructing a new artifact name from the
consumer's attempt would point at an artifact that was never uploaded.

## Optional: run the Azure source for a live comparison

Skip this section if you don't have an authorized Azure DevOps Services project.
Do not create a personal token, organization, or Azure subscription just to finish
the main lesson. This source uses Pipeline Artifact tasks supported by Azure DevOps
Services, not the on-premises Azure DevOps Server artifact tasks.

1. Ask the owner to review the [GitHub repository integration][ado-github] and
   authorize only the learner's workshop repository. Use your own placeholders:
   `https://dev.azure.com/YOUR_ORGANIZATION/YOUR_PROJECT` and
   `https://github.com/YOUR_OWNER/YOUR_PETS_REPOSITORY`, not someone else's tenant.
   Hosted agent parallel-job capacity must be available.
2. In that project's **Pipelines > New pipeline**, select **GitHub**, the connected
   workshop repository, and **Existing Azure Pipelines YAML file**. Select the
   branch containing this example and the path
   `/content/github-actions/solutions/16-migration/azure-pipelines.yml`.
3. Review before saving. Keep `trigger: none` and `pr: none`; don't enable UI
   trigger overrides, schedules, resource triggers, or deployment connections.
   Saving a pipeline definition is an explicit owner-authorized action.
4. Use **Run pipeline** to queue it manually. Select the same unchanged branch tip
   used for the GitHub manual run. Don't push another commit between queues.
5. Compare Azure's source version (`Build.SourceVersion`) with GitHub's run SHA
   (`github.sha`). If they differ, queue matching runs before comparing results.
   PR merge refs and branch heads are not interchangeable.

Record this evidence from **the same commit**:

| Evidence | Compare |
| --- | --- |
| API and browser tests | Same test cases/counts and pass/fail result, not just two green pipeline banners. |
| Toolchain | Python 3.13 and Node 22; note actual patch versions and hosted image versions. |
| Build | Both `npm ci` and `npm run build` pass; the archive contains the expected Astro server/client output. |
| Artifact handoff | Each pipeline downloads its own producer's artifact and verifies its checksums and `commit.txt`. |
| Diagnostics | A failed browser test leaves its report available and its job failed on both platforms. |
| Gate | A failed, skipped, or cancelled required job cannot satisfy the aggregate gate. |

Independent builds may have different archive hashes because timestamps and
toolchain patches can differ. Compare behavior and contents across platforms;
require checksum identity only between a producer and its own downloaded artifact.
If you only ran GitHub, label the Azure side as a static review, not observed
execution parity.

## Exercise controlled failures

Use a practice branch and restore each deliberate change before the next check.

1. Add `exit 1` immediately after the browser-test command. This preserves a report
   from the completed suite while making `test-e2e` fail. Dispatch the branch.
   Confirm the diagnostic upload still runs and `migration-passed` fails. If using
   Azure, make the equivalent source change and queue the same commit.

    ```yaml
    run: |
      npm run test:e2e -- --project=chromium
      exit 1
    ```

   Keep the step's existing `working-directory` and `env` entries.
2. Restore that change, then temporarily break one browser assertion to inspect a
   real failure report and first-retry trace. Restore the assertion afterward.
3. Change the GitHub download's `artifact-ids` to `'1'`. Confirm the missing artifact
   fails `verify` and the gate, rather than causing a rebuild. Restore the producer
   output reference.
4. Insert `printf 'changed' >> site.tar.gz` just before checksum verification.
   Confirm changed bytes also fail the gate, then remove the injected change.
5. Dispatch the restored workflow. After a successful run, rerun only `verify` from
   its job menu and confirm it still finds the original producer's artifact ID.
   The artifact must still be within retention. A missing/expired artifact needs a
   full new run, not a fallback to someone else's latest build.

The gate uses `always()` to inspect every dependency. Its shell step requires
exactly `success` on GitHub and `Succeeded` on Azure, rejecting skipped or
cancelled dependencies and Azure's `SucceededWithIssues`. `continue-on-error` is
not a migration fix. Diagnostic uploads use `!cancelled()` or `not(canceled())`,
so failure evidence is retained without doing unnecessary work after cancellation.

## Plan the CI cutover

1. Keep the translation manual until normal and controlled-failure comparisons
   pass. With no Azure account, stop at the GitHub exercise and a written plan.
2. For a real migration, inventory triggers for the actual repository provider:
   - Azure YAML `trigger` maps to GitHub `push`, with explicit branch/path filters.
     `trigger: none` also avoids Azure's implied CI trigger.
   - Azure YAML `pr` applies to GitHub and Bitbucket Cloud repositories.
     **Azure Repos Git uses branch-policy build validation**, not YAML `pr`.
     `pr: none` does not remove an Azure Repos branch policy.
   - Azure `batch: true` waits for a current branch run, then builds accumulated
     changes. GitHub concurrency and `cancel-in-progress` are different controls,
     not a direct batching translation. Test the intended queue/cancellation
     behavior and account for replaced pending runs.
   - Port schedules, completion/resource triggers, path filters, and draft/fork PR
     behavior separately. Preserve the tested commit semantics.
3. After review, add read-only `pull_request` and `push` triggers for your default
   branch to **the installed copy**. Keep `workflow_dispatch`. Don't use
   `pull_request_target` to run untrusted PR code, add credentials, or add deployment.
4. Open a trial PR and observe `migration-passed` in its checks. Confirm the event
   and branch/path filters cover every PR where this check will be required.
   A manual run alone doesn't establish PR-check coverage.
5. Have the owner add the now-visible `migration-passed` check to the GitHub
   ruleset, selecting its GitHub Actions source where supported. Keep the old
   required check while observing agreed parity across representative commits.
   Preserve any unrelated `tests-passed` or `capstone-passed` requirements.
6. Only after that evidence and owner approval, remove the old CI requirement and
   disable the corresponding Azure automatic CI/PR triggers, UI overrides,
   schedules, and build-validation policy as applicable. Don't disable a still-
   required check first and strand every PR waiting for it.
7. Retain the old definition and run evidence for rollback. If regression appears,
   restore the old CI trigger and its required check before retiring the new check.

This cutover is for **read-only CI only**. Two systems may compare tests and builds;
they must not both deploy the same application. Keep production deployment under
one owner and one active path until a separately reviewed migration is complete.

### Controls that need a separate migration

- **Service connections and OIDC:** an Azure service connection isn't a GitHub
  secret or an automatically portable trust relationship. Reconfigure the cloud
  identity's federated credential for GitHub's issuer, audience, and exact
  repository/ref or environment subject. Grant `id-token: write` only to an
  authorized deployment job and retain least-privilege Azure role assignments.
  No such job or credential belongs in this lab.
- **Environments and approvals:** recreate GitHub environment reviewers, branch/tag
  restrictions, self-review policy, and secret access. Merely writing the old
  environment's name in YAML doesn't transfer its protection. Feature availability
  depends on the GitHub plan and repository visibility.
- **Agent pools:** re-establish runner-group access, labels, network routes,
  isolation, and lifecycle controls. Don't reuse a persistent trusted agent for
  untrusted pull requests.
- **Classic releases and gates:** inventory GUI-defined stages, artifact/version
  selection, tasks, and deployment gates separately. Importer can dry-run classic
  release conversion, but it doesn't migrate all approvals/gates. GitHub workflows
  have no equivalent classic release editor. Unknown tasks, credentials, and
  unsupported gates need manual redesign and validation.

## Optional: assess an existing pipeline with GitHub Actions Importer

The manual translation above is complete without Importer. This optional path
reads an authorized existing Azure DevOps project; it isn't an offline converter
that requires no credentials.

1. Read the current [Azure DevOps Importer guide][importer] and [CLI
   prerequisites][importer-cli]. You need GitHub CLI, Docker running Linux
   containers, access to the GitHub Container Registry, and permission to inspect
   the selected Azure DevOps project. Follow [GHCR authentication guidance][ghcr]
   if registry access requires authentication: a PAT (classic) with `read:packages`
   permits image downloads, with SSO authorization when required. Registry login
   is separate from configuring the Azure connection. Check your organization's
   tool policy and Docker licensing before installing; no paid AI call is involved.
2. The guide currently specifies a GitHub PAT (classic) with `workflow` scope and
   an Azure DevOps PAT with **Read** access to Agent Pools, Build, Code, Release,
   Service Connections, Task Groups, and Variable Groups. Use an owner-approved,
   short-lived credential, not a token pasted into YAML or shell history. Don't
   broaden scopes to work around an unexplained error.
3. In an approved local working directory excluded from version control, install
   and configure the extension:

    ```bash
    gh extension install github/gh-actions-importer
    gh actions-importer -h
    gh actions-importer configure
    gh actions-importer update
    ```

   In `configure`, select **Azure DevOps** and enter `YOUR_ORGANIZATION` and
   `YOUR_PROJECT`, plus the approved credentials at the interactive prompts.
   Keep `.env.local`, logs, fetched pipeline definitions, and reports out of
   commits. Audit output can contain internal metadata even if no secret is shown.
4. Review command scope with `--help`, then run only the approved operations:

    ```bash
    gh actions-importer audit azure-devops --help
    gh actions-importer forecast azure-devops --help
    gh actions-importer dry-run azure-devops pipeline --help

    gh actions-importer audit azure-devops --output-dir importer-output/audit
    gh actions-importer forecast azure-devops --output-dir importer-output/forecast
    gh actions-importer dry-run azure-devops pipeline \
      --pipeline-id YOUR_PIPELINE_ID \
      --output-dir importer-output/dry-run
    ```

   Replace `YOUR_PIPELINE_ID` with the numeric build pipeline definition ID, not
   an individual run/build ID. Configure the intended organization/project first.
   `audit` may enumerate multiple pipelines/projects; verify the approved scope
   before executing it. `forecast` uses historical runs (seven days by default),
   so a new empty project can't produce representative usage estimates.
5. Inspect `audit_summary.md`, `forecast_report.md`, conversion warnings, and
   generated workflows. A `dry-run` writes files but does not open a PR. Compare
   those files against this lesson's command, artifact, permission, and gate
   contracts before activating anything.

`migrate` opens a pull request in a target GitHub repository. That is a separate
write operation requiring explicit authorization, not the next automatic step in
this exercise. A generated PR still needs review and the manual configuration
above. Importer doesn't transfer secrets, service connections, self-hosted agents,
environments, or pre-deployment approvals; pre/post-deployment gates,
post-deployment approvals, and some resource triggers are unsupported.

## Summary and next steps

You've translated real Pets checks, preserved the build/report handoff and failure
gate, and separated a read-only CI cutover from deployment authorization. Return
to the [workshop overview][walkthrough-next] or revisit [artifacts][artifacts] and
[protected environments][environments] before planning a production migration.

## Resources

- [GitHub's Azure Pipelines migration guide][migration]
- [Azure DevOps migration with GitHub Actions Importer][importer]
- [GitHub Actions Importer CLI prerequisites][importer-cli]
- [GitHub Container Registry authentication][ghcr]
- [Build a GitHub repository with Azure Pipelines][ado-github]
- [Azure push triggers][ado-trigger] and [PR trigger/provider rules][ado-pr]
- [Azure expression and dependency syntax][ado-expressions]
- [UsePythonVersion@0][ado-python] and [UseNode@1][ado-node]
- [PublishPipelineArtifact@1][ado-publish] and [DownloadPipelineArtifact@2][ado-download]

| [Previous: Capstone][walkthrough-previous] | [Next: Workshop overview][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[walkthrough-previous]: 15-capstone.md
[walkthrough-next]: README.md
[setup]: 0-setup.md
[testing]: 3-running-tests.md
[artifacts]: 10-artifacts-and-reports.md
[environments]: 12-protected-environments.md
[source]: solutions/16-migration/azure-pipelines.yml
[solution]: solutions/16-migration/migrated-ci.yml
[migration]: https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/manual-migrations/migrate-from-azure-pipelines
[importer]: https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/automated-migrations/azure-devops-migration
[importer-cli]: https://github.com/github/gh-actions-importer
[ghcr]: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry
[ado-github]: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/github?view=azure-devops
[ado-trigger]: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/trigger?view=azure-pipelines
[ado-pr]: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/pr?view=azure-pipelines
[ado-expressions]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/expressions?view=azure-devops
[ado-python]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/use-python-version-v0?view=azure-pipelines
[ado-node]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/use-node-v1?view=azure-pipelines
[ado-publish]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines
[ado-download]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/download-pipeline-artifact-v2?view=azure-pipelines
