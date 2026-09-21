# Creating Custom Actions

| [← Deploy to Azure][walkthrough-previous] | [Next: Reusable Workflows →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

Custom actions let you encapsulate reusable logic into a single step you can use across workflows. GitHub Actions supports three types of custom actions: **[composite][creating-composite-action]** (combines multiple steps), **[JavaScript][creating-javascript-action]** (runs Node.js code), and **[Docker container][creating-docker-container-action]** (runs in a container). Composite actions are the most approachable and a great starting point for bundling common step patterns.

In this exercise you'll create a composite action that sets up Python, preserves dependency caching, and installs the API libraries, then use it in your CI workflow.

## Scenario

The shelter's API and browser jobs repeat Python setup and dependency installation. We'll bundle these steps without changing test behavior. API unit tests use an in-memory database, while the existing Playwright launcher seeds its own isolated database. A setup action shouldn't seed an unrelated database or overwrite the shelter's data.

## Background

The great advantage to a composite action is it builds upon the knowledge you already have. You've defined actions already, and a custom action uses a very similar syntax, all defined in YAML.

Every custom action is defined by an `action.yml` file. This file describes the action's interface and behavior:

- **`name`**: A human-readable name for the action.
- **`description`**: A short summary of what the action does.
- **`inputs`**: Parameters the caller can pass to the action.
- **`outputs`**: Values the action makes available to subsequent steps.
- **`runs`**: Defines how the action executes. Composite actions use `runs.using: 'composite'` with a list of `steps`.

Inputs and outputs let the action communicate with the calling workflow, making the action flexible and reusable across different contexts.

## Create the setup-python-env action

Let's create a composite action with a small, validated interface.

1. In your codespace, open a terminal window by selecting <kbd>Ctl</kbd>+<kbd>\`</kbd>.
2. Create the directory for the action by executing the following command in the terminal:

    ```bash
    mkdir -p .github/actions/setup-python-env
    ```

3. In the newly created `setup-python-env` folder, create a new file named `action.yml` to store your composite action.
4. Add the following YAML to the file to define your composite action:

    ```yaml
    name: Setup Python Environment
    description: Validate the Python version, cache packages, and install the Pets API dependencies
    inputs:
      python-version:
        description: Supported Python version (3.12, 3.13, or 3.14)
        required: false
        default: '3.13'
    outputs:
      python-version:
        description: Resolved Python version installed by setup-python
        value: ${{ steps.python.outputs.python-version }}
    runs:
      using: composite
      steps:
        - name: Validate Python version
          shell: bash
          env:
            PYTHON_VERSION: ${{ inputs.python-version }}
          run: |
            case "$PYTHON_VERSION" in
              3.12|3.13|3.14) ;;
              *) echo "::error::Choose Python 3.12, 3.13, or 3.14."; exit 1 ;;
            esac
        - name: Set up Python
          id: python
          uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
          with:
            python-version: ${{ inputs.python-version }}
            cache: pip
            cache-dependency-path: app/server/requirements.txt
        - name: Install Python dependencies
          shell: bash
          run: python -m pip install -r app/server/requirements.txt
    ```

> [!NOTE]
> Composite action steps must include `shell: bash` for every `run` step — this is required even though it seems redundant. Without it, the workflow will fail with a validation error.

Review the key parts of the action:
- **Inputs** default to Python 3.13 and only accept the three supported minor versions. Input text goes through `env`, not generated shell syntax.
- **Outputs** expose the setup action's resolved Python version without accepting arbitrary output-file content.
- **Caching** still hashes `app/server/requirements.txt`. Refactoring doesn't remove installation or the dependency path.
- Each `run` step explicitly declares `shell: bash` as required by composite actions.

## Use the action in the CI workflow

1. Open `.github/workflows/run-tests.yml`. In `test-api`, keep checkout first and replace **Set up Python** and **Install Python dependencies** with:

    ```yaml
          - name: Set up Python environment
            id: python
            uses: ./.github/actions/setup-python-env
            with:
              python-version: ${{ matrix.python-version }}
    ```

2. Add a step to show how callers consume the output, then keep the isolated API test step:

    ```yaml
          - name: Record Python version
            env:
              PYTHON_VERSION: ${{ steps.python.outputs.python-version }}
            run: |
              printf 'API runtime: Python %s\n' "$PYTHON_VERSION" >> "$GITHUB_STEP_SUMMARY"

          - name: Run tests
            working-directory: app/server
            env:
              DATABASE_PATH: ':memory:'
            run: python -m unittest test_app -v
    ```

3. In `test-e2e`, replace only the Python setup and install steps with the default call:

    ```yaml
          - name: Set up Python environment
            uses: ./.github/actions/setup-python-env
    ```

4. Keep Node 22, npm caching with `app/client/package-lock.json`, browser installation, and the Playwright command unchanged. Keep the whole `build-client` job, workflow permissions, PR concurrency, bytecode setting, and job timeouts.
5. Compare both complete solution files before committing:

    | Solution | Install destination |
    |---|---|
    | [run-tests.yml][ci-solution] | `.github/workflows/run-tests.yml` |
    | [setup-python-env/action.yml][action-solution] | `.github/actions/setup-python-env/action.yml` |

    This stage changes CI only. Keep the previous deployment workflow if you opted into Azure; no Azure setup is required for the composite action.

6. In the terminal, commit and push your changes:

    ```bash
    git add .github/actions/setup-python-env/action.yml .github/workflows/run-tests.yml
    git commit -m "Add setup-python-env composite action"
    git push
    ```

7. Navigate to the **Actions** tab on GitHub and verify the workflow runs successfully with the new action.

Checkout must precede a local `uses: ./...` action, because its metadata is read from the checked-out repository. Composite actions inherit their caller job's permissions and timeout; they don't request separate credentials or provision a runner.

## Check input validation

1. On a practice branch, temporarily call the action with `python-version: 'not-a-version'` in the e2e job.
2. Open a PR and confirm the action fails at **Validate Python version**, before installing dependencies.
3. Restore the default call and push again. Confirm the new run passes and the setup logs still show pip caching.

> [!TIP]
> When developing custom actions, you can test them by pushing to a branch and triggering a workflow run. Check the workflow logs to ensure each step in your composite action executes as expected.

## Types of custom actions

GitHub Actions supports three types of custom actions, each suited to different use cases:

| Type | Best for | Runs on | Complexity |
|------|----------|---------|------------|
| **Composite** | Bundling multiple existing steps into one | Directly on the runner | Easiest to create |
| **JavaScript** | Complex logic, API calls, or custom computations | Node.js runtime | Moderate |
| **Docker container** | Actions that need specific tools or environments | Inside a container | Most involved |

- **Composite actions** combine related steps, such as setup, caching, and installation, using the same step syntax you already know.
- **JavaScript actions** are best when you need custom logic, such as making API calls, processing data, or interacting with the GitHub API. They run on Node.js and have access to the `@actions/core` and `@actions/github` packages.
- **Docker container actions** are best when your action requires specific tools, operating system libraries, or a particular runtime environment. They run in a Docker container, giving you full control over the execution environment.

## Summary and next steps

You've created a composite action for validated Python setup, caching, and installation, with an output the caller can use. Tests keep control of their own database lifecycle.

Next, we'll take reusability to the next level by exploring [reusable workflows][walkthrough-next] for sharing entire workflow patterns across your CI/CD pipeline.

## Resources

- [Creating a composite action][creating-composite-action]
- [About custom actions][about-custom-actions]
- [Metadata syntax for GitHub Actions][metadata-syntax]
- [GitHub Skills: Reusable workflows][skills-reusable-workflows]

| [← Deploy to Azure][walkthrough-previous] | [Next: Reusable Workflows →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[about-custom-actions]: https://docs.github.com/actions/sharing-automations/creating-actions/about-custom-actions
[action-solution]: solutions/07-custom-actions/setup-python-env/action.yml
[ci-solution]: solutions/07-custom-actions/run-tests.yml
[creating-composite-action]: https://docs.github.com/actions/sharing-automations/creating-actions/creating-a-composite-action
[creating-docker-container-action]: https://docs.github.com/actions/sharing-automations/creating-actions/creating-a-docker-container-action
[creating-javascript-action]: https://docs.github.com/actions/sharing-automations/creating-actions/creating-a-javascript-action
[deploy-azure]: 6-deploy-azure.md
[metadata-syntax]: https://docs.github.com/actions/sharing-automations/creating-actions/metadata-syntax-for-github-actions
[skills-reusable-workflows]: https://github.com/skills/reusable-workflows
[walkthrough-previous]: 6-deploy-azure.md
[walkthrough-next]: 8-reusable-workflows.md
