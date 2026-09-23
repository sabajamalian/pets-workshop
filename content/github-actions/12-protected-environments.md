# Protected Environments

| [Previous: Runners and hardware][walkthrough-previous] | [Next: GitHub Copilot CLI][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

## Scenario

The shelter reviews code before merging, but also wants a volunteer to approve
when a release can proceed. These are different decisions: a branch ruleset controls
merging, while an environment protection rule controls entry to a deployment job.

We'll first practice approval using artifact verification only. No Azure resources,
credentials, or deployments are needed for that exercise.

## Background

A job that references a GitHub **environment** can wait for a reviewer and restrict
which branches or tags may deploy. Environment secrets become available to that
job only after its protection rules pass.

The environment must be configured by an owner **before** the workflow runs.
Referencing a new name in YAML can create an environment without the protection
rules you intended.

> [!IMPORTANT]
> Required reviewers are available for public repositories on GitHub Free, Pro,
> and Team. Private-repository availability differs by plan; check the
> [current requirements][environment-docs]. Preventing self-review requires another
> eligible person to approve. If you cannot configure the rules, read through the
> lab with your instructor; do not remove the gate and call it equivalent.

## Configure an approval boundary

1. As a repository owner, open **Settings > Environments** and create
   `pets-production`.
2. Add a required reviewer and enable **Prevent self-review**.
3. Under deployment branches and tags, choose **Selected branches and tags** and
   allow the `main` branch only. These lessons assume `main` is the default branch.
4. Disable administrator bypass where available and appropriate to your exercise.
5. Leave secrets empty. The first workflow only verifies an artifact.

A branch restriction applies to the workflow run's ref, not necessarily a different
ref that a checkout step requests. Keep workflow code trusted and review rollback
inputs separately.

## Run the credential-free exercise

1. Copy the [complete protected verification workflow][solution]:

    ```bash
    mkdir -p .github/workflows
    cp content/github-actions/solutions/12-environments/protected-release.yml .github/workflows/protected-release.yml
    ```

2. Review the jobs. `build` packages the frontend, `verify` checks it before anyone
   is asked for approval, and `approve` references `pets-production`.
3. Commit and push to `main` in your workshop repository, using a reviewed PR if
   you enabled the ruleset. Dispatch **Protected Release Verification**.
4. Confirm `verify` passes before the last job waits for approval.
5. Ask the configured reviewer to inspect the commit, build result, and artifact,
   then approve it. The final job downloads and rechecks the same artifact.
6. Confirm the summary says nothing was deployed.

All three jobs use read-only repository permissions. A successful approval does
not turn checksum verification into a provenance guarantee.

## Diagnose a missing approval

1. Have the initiating user try to approve their own run. Confirm self-review is
   rejected.
2. Have the eligible reviewer reject a separate run and confirm the final job
   cannot succeed.
3. Dispatch from a practice branch. The solution refuses to build outside `main`;
   do not remove that guard to bypass the environment policy.
4. If a job starts without waiting, stop and inspect the exact environment name,
   reviewers, bypass settings, and plan support before using it for a real release.

## Optional: protect the Azure deployment

Complete the [Azure][azure] and [reusable workflow][reuse] exercises first. This
extension provisions or updates Azure resources and may incur charges.

1. Keep the owner-approved repository variables from `azd pipeline config`.
   GitHub environment names and the `AZURE_ENV_NAME` used by azd are separate
   settings; naming one does not configure the other.
2. Configure the Azure application's federated credential for the GitHub
   environment. For a repository using name-based OIDC subjects, the subject is:

    ```text
    repo:OWNER/REPOSITORY:environment:pets-production
    ```

    Use issuer `https://token.actions.githubusercontent.com` and the Azure audience
    `api://AzureADTokenExchange`. Replace the owner/repository exactly. If your
    repository uses immutable ID-based subjects or your organization customizes
    them, match the actual subject under that policy instead.

3. Set `environment-name: pets-production` on the reusable deployment call from
   the previous lesson. The reusable workflow assigns that environment to its
   actual deployment job. Keep `id-token: write` only where authentication needs it.
4. Confirm automatic CD still accepts only a successful same-repository `main`
   push CI run and checks out its exact `head_sha`.
5. Have the owner review all Azure trust relationships. A remaining branch-scoped
   federated credential can still allow other matching workflows to authenticate
   without this environment. Retire that path only after reviewing its consumers.
6. Test the approved path on disposable Azure resources. Confirm a declined
   approval prevents authentication and deployment.

An environment changes the default OIDC subject; the original branch-based
credential may stop matching. Diagnose that mismatch rather than adding a stored
client secret or broadening trust indiscriminately.

The [capstone][capstone] includes an optional protected deployment call. It still
uses `azd up`, which may rebuild from the verified commit. Immutable image promotion,
staging, attestations, and automatic rollback remain separate follow-on exercises.
When finished with a disposable Azure environment, an owner can review `azd down`
and its deletion prompt; it removes that environment's resources.

## Summary and next steps

You've separated merge approval from release approval and observed a protected job
without cloud access. Next, we'll use the same principle for an optional
[read-only Copilot CLI run][walkthrough-next].

## Resources

- [Environments and deployment protection rules][environment-docs]
- [Reviewing deployments][reviews]
- [Configuring OIDC in Azure][azure-oidc]

| [Previous: Runners and hardware][walkthrough-previous] | [Next: GitHub Copilot CLI][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[walkthrough-previous]: 11-runners-and-hardware.md
[walkthrough-next]: 13-copilot-cli.md
[solution]: solutions/12-environments/protected-release.yml
[azure]: 6-deploy-azure.md
[reuse]: 8-reusable-workflows.md
[capstone]: 15-capstone.md
[environment-docs]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
[reviews]: https://docs.github.com/actions/managing-workflow-runs-and-deployments/managing-deployments/reviewing-deployments
[azure-oidc]: https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-azure
