# Deploying to Azure with azd

| [← Matrix Strategies & Parallel Testing][walkthrough-previous] | [Next: Creating custom actions →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

With CI in place, it's time for CD — continuous deployment or continuous delivery. We'll use the [Azure Developer CLI (azd)][azd-docs], Microsoft's recommended tool for deploying to Azure. **azd** handles the heavy lifting: generating infrastructure-as-code (Bicep), configuring passwordless authentication (OIDC), and creating the GitHub Actions workflow.

## Scenario

With the prototype built, the shelter is ready to share their application with the world! They want to deploy automatically whenever code is pushed to `main` — but only after CI passes.

## Background

> [!IMPORTANT]
> This is an optional, owner-operated Azure lab. Provisioning creates billable resources and `azd pipeline config` changes Azure identity and repository configuration. Continue only with an approved subscription and the required permissions. If unavailable, review the solution without installing it and continue to lesson 7.

### Secrets and variables

Speaking of secrets and variables... In a prior exercise you utilized `GITHUB_TOKEN`. `GITHUB_TOKEN` is a special secret automatically available to every workflow, and provides access to the current repository. You can add your own secrets and variables to your repository for use in workflows.

Secrets hold passwords and other sensitive values. Add them through the CLI, APIs, or repository settings; GitHub doesn't reveal their values again through the settings UI. Masking helps prevent accidental log exposure but isn't a guarantee, so never print credentials. Anyone able to change code that runs with a secret may be able to disclose it.

Variables, on the other hand, are designed to be public values. They're settings like URLs or names, or other values that aren't sensitive. Variables can be both read and written. Use variables whenever you need the ability to configure a value outside a workflow.

### Protecting production

In a later exercise we'll configure **branch rulesets** to require CI checks and reviews before merging to `main`. This lesson separately checks that post-merge CI succeeded and deploys that exact commit. A successful PR run isn't authorization to deploy.

> [!TIP]
> GitHub **environments** add deployment-time controls such as human approval. Branch rulesets control merging; they aren't equivalent to environment protection. The [protected environments lesson][protected-environments] adds that separate control and updates the Azure federated identity to match it.

## Install and initialize azd

Let's set up the Azure Developer CLI and scaffold the infrastructure for our project.

1. Open the terminal in your codespace (or press <kbd>Ctl</kbd>+<kbd>`</kbd> to toggle it).
2. Install azd by running:

    ```bash
    curl -fsSL https://aka.ms/install-azd.sh | bash
    ```

3. Log in to Azure:

    ```bash
    azd auth login
    ```

    Follow the device code flow — open the URL shown, enter the code, and sign in with your Azure account.

4. Initialize the project by running:

    ```bash
    azd init --from-code
    ```

5. `azd` will scan your project and detect the client and server services. When prompted, select **Confirm and continue initializing my app** to accept the detected services and generate the project configuration.
6. By default, `azd` generates infrastructure in memory at deploy time. To customize the infrastructure, persist it to disk by running:

    ```bash
    azd infra gen
    ```

7. Explore the generated `infra/` directory. You'll see Bicep files (`.bicep`) that define the Azure resources for your application:

    ```bash
    ls infra/
    ```

> [!TIP]
> Bicep is Azure's domain-specific language for defining infrastructure as code. If you have GitHub Copilot, try asking it to explain the generated Bicep files!

The generated `infra/` directory contains several Bicep files that work together:

- **`main.bicep`** — The entry point. It defines the deployment's parameters (like location and environment name) and orchestrates the other files.
- **`main.parameters.json`** — Default parameter values passed to `main.bicep` at deployment time.
- **`resources.bicep`** — The core of the infrastructure. It defines the Azure Container Apps environment and the individual container apps for the client and server, including their Docker images, environment variables, ingress settings, and scaling rules.
- **`modules/`** — Helper modules referenced by the main files (e.g., for fetching container image metadata).
- **`abbreviations.json`** — A lookup table `azd` uses to generate consistent, short resource names following Azure naming conventions.

## Configure the infrastructure

The generated Bicep files define the Azure Container Apps that will host the client and server. We need to add an environment variable so the client knows where to find the API server.

1. Open `infra/resources.bicep` in your codespace.
2. Find the section (around line 109) that reads:

    ```bicep
    {
      name: 'PORT'
      value: '4321'
    }
    ```

3. Create a new line below the closing `}` and add the following:

    ```bicep
    {
      name: 'API_SERVER_URL'
      value: 'https://${server.outputs.fqdn}'
    }
    ```

> [!NOTE]
> While the syntax resembles JSON, **it's not JSON**. You'll need to resist the natural urge to add commas between the objects!

## Create the CD workflow

By default, `azd pipeline config` can generate a workflow that deploys on every push to `main`. We want a workflow that deploys only after trusted CI passes. Create and review the custom workflow first, then inspect any generated changes before pushing.

Let's create a workflow that:
- Only deploys after a successful, same-repository `main` push run of **Run Tests**, using [`workflow_run`][workflow-run-docs].
- Checks out the successful run's exact commit SHA, not the newest `main` commit.
- Serializes deployments without cancelling an active deployment.

1. Create a new file at `.github/workflows/azure-dev.yml`.
2. Add the following content:

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
        runs-on: ubuntu-latest
        timeout-minutes: 30
        permissions:
          contents: read
          id-token: write
        concurrency:
          group: deploy-production
          cancel-in-progress: false
        env:
          DEPLOY_SHA: ${{ github.event.workflow_run.head_sha }}
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
          - name: Checkout tested code
            uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              ref: ${{ github.event.workflow_run.head_sha }}
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

3. Save the file.

The complete [Azure solution][azure-solution] installs as `.github/workflows/azure-dev.yml`, alongside lesson 5's unchanged `run-tests.yml`. Keep `main` as the training repository's default branch. The CD workflow must exist on the default branch before `workflow_run` can trigger it.

Let's walk through the key parts:

- **`id-token: write`** allows only the deploy job to request a GitHub OIDC token, which Azure exchanges for short-lived access. The CI jobs still have only `contents: read`.
- **`vars.*`** supplies nonsecret Azure configuration through environment variables. No long-lived Azure password or `secrets: inherit` is needed.
- **`workflow_run`** is privileged even when the preceding run wasn't. The condition rejects failed runs, PR events, other branches, and fork repositories. Never replace it with a conclusion-only check or execute artifacts downloaded from an untrusted PR.
- **`head_sha`** identifies the tested source. The checkout and verification step use that exact SHA; `github.sha` in a `workflow_run` workflow refers to the default branch context and isn't a substitute.
- **`concurrency`** allows one active deployment in this repository. `cancel-in-progress: false` avoids interrupting it, but pending runs may be replaced and order isn't guaranteed. This is serialization, not a first-in-first-out release queue.
- **`azd up`** provisions and deploys. It can rebuild the app, so this isn't immutable build-once artifact promotion.

Manual deployment is deliberately absent here. Lesson 8 adds a separate trusted-operator workflow with a default-branch guard and an optional reviewed rollback SHA.

## Set up Azure authentication

Have the subscription and repository owner review the configuration before running `azd`. The identity needs only the Azure roles required by the generated infrastructure at the intended scope.

1. Configure the deployment pipeline:

    ```bash
    azd pipeline config
    ```

2. Follow the prompts — here's what to expect:

    | Prompt | What to select |
    |--------|---------------|
    | **Select a provider** | Choose **GitHub** |
    | **Enter a unique environment name** | Enter a short name (e.g., `<HANDLE>-pets-workshop`) — this names your Azure resource group |
    | **Select an Azure subscription** | Choose the subscription you want to deploy to |
    | **Select an Azure location** | Pick a region close to you (e.g., `eastus2`) |
    | **Select how to authenticate the pipeline to Azure** | Choose **Federated Service Principal (SP + OIDC)** |

    After you answer these, `azd` will:
    - Create OIDC credentials in Azure for passwordless authentication
    - Configure repository values for the selected authentication mode
    - Detect your workflow files; inspect the resulting diff before accepting changes

3. Decline automatic commit and push. Review the generated files and verify that `azure-dev.yml` still has the event guards, exact-SHA checkout, pinned actions, and permissions above.
4. Confirm these repository **variables** exist: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_ENV_NAME`, and `AZURE_LOCATION`. For this OIDC workflow no repository secret is required.
5. In Azure, verify the federated credential's issuer is `https://token.actions.githubusercontent.com`, audience is `api://AzureADTokenExchange`, and subject is `repo:OWNER/REPO:ref:refs/heads/main` for your training repository. Don't grant trust to pull request subjects or arbitrary branches.
6. Only after review, commit the generated application/infrastructure configuration and workflows, then push using your repository's normal process. Don't commit `.azure` state or credentials.

`AZURE_ENV_NAME` is an **azd** environment name, not a GitHub protected environment. This core workflow has no GitHub environment, so it uses branch-based federation. Adding an environment later changes the OIDC subject; follow lesson 12 rather than adding `environment:` without updating Azure trust.

> [!TIP]
> After `azd pipeline config` completes, navigate to **Settings** > **Secrets and variables** > **Actions** > **Variables** tab to see the repository variables it created (like `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, etc.). These are the `vars.*` values your workflow references.

## Test the pipeline

After the owner-approved push, verify both the successful deployment and the rejected paths.

1. Navigate to the **Actions** tab. The push will trigger the **Run Tests** workflow first.
2. Once tests complete successfully, the **Deploy App** workflow will start automatically (via the `workflow_run` trigger).
3. Watch the deploy job run — it will provision Azure resources and deploy both the client and server applications.
4. Once the deployment completes return to your codespace.
5. Run the following in the terminal to list the details of your new Azure environment:

    ```bash
    azd show
    ```

6. Look for the **client** service endpoint in the output.
7. Open the client URL in your browser — you should see the pet shelter application live!

8. Confirm the checkout log's commit is the triggering **Run Tests** run's SHA. A successful PR run should never start the deploy job; a failed main run should leave it skipped.

The pinned setup action fixes its own source, not the downloaded azd CLI release or generated infrastructure. Review generated configuration when azd changes. Local YAML validation can't prove Azure roles, federated trust, or endpoint health; those require this authorized exercise.

## Clean up optional Azure resources

1. When finished with deployment lessons, have the owner select the intended azd environment and run `azd down`. Review the deletion prompt before confirming.
2. Verify resource deletion and remaining billable resources in the Azure portal.
3. Disable the installed deployment workflows when no longer needed. Ask the owner to remove workshop-only federated credentials, role assignments, and repository variables; don't remove identities shared with other projects.

## Summary and next steps

Congratulations! You've deployed the pet shelter application to Azure with a CI/CD pipeline:

- **CI-gated deployment** — CD only runs after CI passes, using `workflow_run`
- **OIDC authentication** — passwordless, short-lived tokens instead of stored credentials
- **Concurrency controls** — preventing conflicting deployments
- **azd integration** — `azd pipeline config` configured credentials around your custom workflow

In a later exercise, we'll add **branch rulesets** to ensure code must pass CI and be reviewed before it can reach `main` — creating a natural production gate.

Next we'll [create custom actions][walkthrough-next] to reduce duplication and make our workflows more maintainable.

## Resources

- [What is the Azure Developer CLI?][azd-docs]
- [Create a custom pipeline definition][azd-pipeline-definition]
- [Events that trigger workflows: workflow_run][workflow-run-docs]
- [About security hardening with OpenID Connect][oidc-docs]
- [Deploying with GitHub Actions][actions-deploy]
- [Using environments for deployment][environments-docs]

| [← Matrix Strategies & Parallel Testing][walkthrough-previous] | [Next: Creating custom actions →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[actions-deploy]: https://docs.github.com/actions/use-cases-and-examples/deploying/deploying-with-github-actions
[azd-docs]: https://learn.microsoft.com/azure/developer/azure-developer-cli/overview
[azure-solution]: solutions/06-deploy-azure/azure-dev.yml
[protected-environments]: 12-protected-environments.md
[azd-pipeline-definition]: https://learn.microsoft.com/azure/developer/azure-developer-cli/pipeline-create-definition
[environments-docs]: https://docs.github.com/actions/managing-workflow-runs-and-deployments/managing-deployments/using-environments-for-deployment
[oidc-docs]: https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect
[running-tests]: 3-running-tests.md
[workflow-run-docs]: https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_run
[walkthrough-previous]: 5-matrix-strategies.md
[walkthrough-next]: 7-custom-actions.md
