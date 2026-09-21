# Reusable Workflows

| [← Creating Custom Actions][walkthrough-previous] | [Next: Rulesets & Core Checkpoint →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

Reusable workflows let you define an entire workflow that other workflows can call, like a function. This is different from custom actions — actions encapsulate individual *steps*, while reusable workflows encapsulate entire *jobs*. They're triggered with the `workflow_call` event and can accept inputs, secrets, and produce outputs.

In this exercise you'll extract the deployment pattern into a reusable workflow, then call it from both your CD pipeline and a new manual deployment workflow for rollbacks and hotfixes.

## Scenario

The shelter deploys the exact commit that passed CI on `main`. The team also needs a trusted operator to redeploy a reviewed commit during recovery. We'll share the deployment steps while keeping automatic CI-gated deployment separate from that manual exception.

This remains an optional Azure exercise with lesson 6's owner, identity, infrastructure, and cost prerequisites. If you skipped Azure, review the files without installing or running them; lesson 9's CI gate doesn't depend on deployment.

## Background

In the [previous exercise][walkthrough-previous] you created a composite action to bundle steps together. Reusable workflows solve a similar problem — avoiding duplication — but at a different level. It's important to understand when to reach for each one.

A **composite action** combines multiple *steps* into a single step that runs inside a job. A **reusable workflow** packages one or more entire *jobs* that a caller workflow references at the job level. Here's a side-by-side comparison:

| | Composite Action | Reusable Workflow |
|---|---|---|
| **What it encapsulates** | Multiple steps, run as a single step | One or more complete jobs |
| **Where it lives** | `action.yml` in any directory (e.g. `.github/actions/`) | `.github/workflows/` directory only |
| **How it's called** | `uses:` inside a job's `steps` | `uses:` directly on a `job`, not inside steps |
| **Runner control** | Runs on the caller job's runner | Each job specifies its own runner |
| **Secrets** | Cannot access secrets directly | Can receive secrets via `secrets:` or `secrets: inherit` |
| **Logging** | Appears as one collapsed step in the log | Every job and step is logged individually |
| **Nesting** | Can call other actions, within GitHub's limits | Can call other workflows, within GitHub's limits |
| **Marketplace** | Can be published to the [Actions Marketplace][actions-marketplace] | Cannot be published to the Marketplace |

**When to use which:**

- Choose a **composite action** when you want to bundle a handful of related steps that run within a single job — like the `setup-python-env` action you just built.
- Choose a **reusable workflow** when you want to share entire job definitions — including runner selection, environment targeting, and concurrency controls — across multiple workflows. Deployment pipelines are a classic use case, which is exactly what we'll build next.

## Understand permissions, variables, and secrets

The Azure configuration from lesson 6 uses repository **variables** and OIDC, not a stored Azure password. The caller grants `contents: read` and `id-token: write` to its deployment job. The called workflow can't elevate permissions beyond what the caller grants.

Keep `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_ENV_NAME`, and `AZURE_LOCATION` as repository variables. The reusable workflow can access those through `vars`. This example needs neither `on.workflow_call.secrets` nor `secrets: inherit`.

If another integration genuinely requires a secret, declare that specific secret under `on.workflow_call.secrets` and pass only it from the caller. `secrets: inherit` forwards a broader set and shouldn't be added by habit. Workflow-level `env` values don't automatically propagate across the caller boundary; use declared inputs, outputs, or repository variables.

## Create a reusable deployment workflow

The reusable workflow requires an exact full commit SHA. There's no implicit fallback to `main` or `github.sha`: the caller must make its source selection explicit.

1. In your codespace, create a new file at `.github/workflows/reusable-deploy.yml`.

2. Define `workflow_call` and the inputs:

    ```yaml
    name: Reusable Deploy Workflow

    on:
      workflow_call:
        inputs:
          deploy-ref:
            description: Exact reviewed full commit SHA to deploy
            required: true
            type: string
          environment-name:
            description: Optional GitHub environment (empty keeps branch-based OIDC)
            required: false
            type: string
            default: ''
    ```

3. Below `on`, add the permissions and job:

    ```yaml
    permissions:
      contents: read

    jobs:
      deploy:
        if: >-
          (github.event_name == 'workflow_run' &&
           github.event.workflow_run.conclusion == 'success' &&
           github.event.workflow_run.event == 'push' &&
           github.event.workflow_run.head_branch == 'main' &&
           github.event.workflow_run.head_repository.full_name == github.repository &&
           inputs.deploy-ref == github.event.workflow_run.head_sha) ||
          (github.event_name == 'workflow_dispatch' &&
           github.ref == format('refs/heads/{0}', github.event.repository.default_branch))
        runs-on: ubuntu-latest
        timeout-minutes: 30
        permissions:
          contents: read
          id-token: write
        environment: ${{ inputs.environment-name }}
        concurrency:
          group: deploy-production
          cancel-in-progress: false
        env:
          DEPLOY_SHA: ${{ inputs.deploy-ref }}
          AZURE_CLIENT_ID: ${{ vars.AZURE_CLIENT_ID }}
          AZURE_TENANT_ID: ${{ vars.AZURE_TENANT_ID }}
          AZURE_SUBSCRIPTION_ID: ${{ vars.AZURE_SUBSCRIPTION_ID }}
          AZURE_ENV_NAME: ${{ vars.AZURE_ENV_NAME }}
          AZURE_LOCATION: ${{ vars.AZURE_LOCATION }}
        steps:
          - name: Validate deployment SHA
            shell: bash
            run: |
              [[ "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::Expected a full commit SHA."; exit 1; }
          - name: Checkout reviewed code
            uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              ref: ${{ inputs.deploy-ref }}
              persist-credentials: false
          - name: Verify checkout
            run: test "$(git rev-parse HEAD)" = "$DEPLOY_SHA"
          - name: Install azd
            uses: Azure/setup-azd@c495e71ba59e44bfaaac10a32c8ee90d191ca4a3 # v2.2.1
          - name: Log in with Azure (Federated Credentials)
            run: |
              azd auth login \
                --client-id "$AZURE_CLIENT_ID" \
                --federated-credential-provider github \
                --tenant-id "$AZURE_TENANT_ID"
          - name: Provision and deploy
            run: azd up --no-prompt
    ```

> [!NOTE]
> Reusable workflow files must be directly in `.github/workflows`, and callers invoke them at the job level, not inside `steps`. Runner timeouts belong to jobs inside the called workflow. GitHub's [current reusable workflow limits][workflow-limits] apply to nesting and distinct called workflows; don't build a design around a remembered numeric limit.

The repeated trust guard protects the called workflow too. Automatic calls must carry the exact successful run's `head_sha`. Manual calls must originate from the default branch, and the input still has to pass SHA validation before checkout.

Leave `environment-name` empty in the core workshop. Empty means **no GitHub environment**, preserving lesson 6's branch-based OIDC subject. It's different from `AZURE_ENV_NAME`. Lesson 12 shows how to select a protected GitHub environment and update the Azure federated subject together.

## Update the CD workflow

Now update your `azure-dev.yml` to call the reusable workflow instead of defining the deploy steps inline.

1. Replace the contents of `.github/workflows/azure-dev.yml` with:

    ```yaml
    name: Deploy App

    on:
      workflow_run:
        workflows: ["Run Tests"]
        branches: [main]
        types: [completed]

    permissions:
      contents: read

    jobs:
      deploy:
        if: >-
          github.event.workflow_run.conclusion == 'success' &&
          github.event.workflow_run.event == 'push' &&
          github.event.workflow_run.head_branch == 'main' &&
          github.event.workflow_run.head_repository.full_name == github.repository
        permissions:
          contents: read
          id-token: write
        uses: ./.github/workflows/reusable-deploy.yml
        with:
          deploy-ref: ${{ github.event.workflow_run.head_sha }}
    ```

    Notice how the entire job definition is replaced by a single `uses:` reference. The reusable workflow handles checkout, authentication, and deployment — the caller just decides *when* to deploy.

## Create a manual deploy workflow

Now add a separate manual path for trusted operators. A manual run isn't covered by the automatic CI gate, even when its default is the current main commit. Review the selected commit, prior test results, and its deployment configuration before authorizing it.

1. Create a new file at `.github/workflows/manual-deploy.yml`.
2. Add the following content:

    ```yaml
    name: Manual Deploy

    on:
      workflow_dispatch:
        inputs:
          rollback-ref:
            description: Optional reviewed full commit SHA for rollback (empty deploys this main run's SHA)
            required: false
            type: string
            default: ''

    permissions:
      contents: read

    jobs:
      deploy:
        if: github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
        permissions:
          contents: read
          id-token: write
        uses: ./.github/workflows/reusable-deploy.yml
        with:
          deploy-ref: ${{ inputs.rollback-ref || github.sha }}
    ```

    Select the default branch (`main`) in **Run workflow**. A run from another branch skips deployment. Empty `rollback-ref` uses this dispatch run's exact SHA; for rollback, supply a reviewed 40-character lowercase commit SHA, not a moving branch or tag. Full-SHA validation prevents ambiguous selection, but doesn't prove the code is trustworthy.

3. In the terminal (<kbd>Ctl</kbd>+<kbd>`</kbd> to toggle), commit and push your changes:

    ```bash
    git add .github/workflows/reusable-deploy.yml .github/workflows/azure-dev.yml .github/workflows/manual-deploy.yml
    git commit -m "Extract reusable deploy workflow and add manual deploy"
    git push
    ```

4. With owner approval, verify the automatic deployment uses the successful push's SHA. Then use **Manual Deploy** for a reviewed commit and verify its checkout log too. Do not deploy a fork's commit or use an unreviewed rollback ref.

Only trusted operators with repository access should be allowed to run this workflow, and branch rules must protect changes to the workflow and deployment code. The branch guard prevents accidental nondefault dispatch, not a malicious authorized editor. Lesson 12 adds deployment-time approval.

## Install and verify the complete solution

1. Compare these files with your edits. They install together:

    | Solution | Install destination |
    |---|---|
    | [azure-dev.yml][auto-solution] | `.github/workflows/azure-dev.yml` (replaces lesson 6) |
    | [reusable-deploy.yml][reusable-solution] | `.github/workflows/reusable-deploy.yml` |
    | [manual-deploy.yml][manual-solution] | `.github/workflows/manual-deploy.yml` |

2. Keep lesson 7's `run-tests.yml` and `.github/actions/setup-python-env/action.yml` unchanged.
3. Review rejected cases without changing the production trust policy: a failed CI run, a PR run, or a different head repository must not deploy. A malformed manual SHA must fail before checkout or Azure login.
4. Keep `deploy-production` concurrency in the called job so both callers share it. Don't add an identical caller-level cancellation group. Pending deployments may be replaced; this isn't an ordered release queue.

> [!TIP]
> When viewing a workflow run that calls reusable workflows, GitHub shows each caller job separately. Select a job to see the steps from the reusable workflow running inside it.

This pattern keeps your deployment logic in one place. When you need to update the deployment process — like adding health checks or notifications — you change it once in the reusable workflow and every caller benefits.

## Summary and next steps

Reusable workflows reduce duplication at the workflow level. You've extracted the shared deployment pattern into a template that both the automated CD pipeline and the manual deploy workflow call with a single `uses` reference. This keeps your deployment process maintainable as it grows — any change happens in one place.

Next, we'll ensure quality gates are enforced with [branch protection, required workflows, and more][walkthrough-next].

## Resources

- [Reusing workflows][reusing-workflows]
- [The `workflow_call` event][workflow-call-event]
- [Sharing workflows with your organization][sharing-workflows]
- [GitHub Skills: Reusable workflows][skills-reusable-workflows]

| [← Creating Custom Actions][walkthrough-previous] | [Next: Rulesets & Core Checkpoint →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[actions-marketplace]: https://github.com/marketplace?type=actions
[auto-solution]: solutions/08-reusable-workflows/azure-dev.yml
[manual-solution]: solutions/08-reusable-workflows/manual-deploy.yml
[reusable-solution]: solutions/08-reusable-workflows/reusable-deploy.yml
[workflow-limits]: https://docs.github.com/actions/reference/workflows-and-actions/reusing-workflow-configurations#limitations-of-reusable-workflows
[reusing-workflows]: https://docs.github.com/actions/sharing-automations/reusing-workflows
[sharing-workflows]: https://docs.github.com/actions/sharing-automations/sharing-workflows-secrets-and-runners-with-your-organization
[skills-reusable-workflows]: https://github.com/skills/reusable-workflows
[workflow-call-event]: https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_call
[walkthrough-previous]: 7-custom-actions.md
[walkthrough-next]: 9-required-workflows.md
