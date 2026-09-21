# Running Tests

| [← Securing the Development Pipeline][walkthrough-previous] | [Next: Caching →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

Now that you know the basics of GitHub Actions and have seen how GitHub uses it for code scanning, it's time to build your own workflow. In this exercise you'll create a **continuous integration (CI)** pipeline that automatically runs the shelter's tests.

## Scenario

The shelter's app is growing, and the team wants to make sure new changes don't break existing functionality. The application has two test suites: **unit tests** for the Flask API, and **end-to-end (e2e) tests** that use [Playwright][playwright] to test the full stack in a browser. We'll run both, plus an Astro production build, on every push and pull request (PR) to `main`.

## Background

As you saw in the [introduction][introduction], the `on` declaration specifies when a workflow will run. For true automation, you'll use `on` to indicate the [triggers][workflow-triggers] for the workflow to run automatically. In our scenario, this will be whenever a PR is made to the `main` branch, or when code is pushed or merged into it.

Most workflows have a relatively common set of tasks. You typically need to install libraries, perform builds, and run various commands. Rather than having to script everything out by hand, there's a collection of available actions in a marketplace - the aptly named [Actions Marketplace][actions-marketplace]. There you can find pluggable, reusable actions, ready to be added to any workflow.

## Using the Actions Marketplace

The [Actions Marketplace][actions-marketplace] contains tens of thousands of community created actions. These include those from OSS contributors of all sizes, and vendors to allow for quick integration of their products.

For most actions, you can just add the name of the action, typically `vendor/action-name`, the necessary configuration, and it's now part of your workflow!

### Security and the Actions Marketplace

The marketplace offers various protections to ensure you're using the right action at the right time. For starters, creators can be [verified][marketplace-badges] by GitHub, giving you the confidence the organization who says they built an action is the one who actually built it.

Pin third-party actions to a reviewed full commit SHA with a version comment. Tags and branches can move; a [SHA reference][action-versioning] fixes the action source revision. Review both the source and any tools it downloads.

## Create the CI workflow

Our application has a Flask backend with unit tests, and an Astro frontend that's validated with end-to-end tests. Let's begin building a workflow to run these tests. We'll start with the unit tests, then add the end-to-end tests a bit later in this lesson.

To run the unit tests, you'll need to do the following in the workflow:

- checkout the code.
- install Python.
- install the necessary Python libraries.
- run the tests.

Let's build that out!

1. In your codespace, create a new file named `.github/workflows/run-tests.yml`.
2. Start with this workflow header. This is a partial snippet; it needs the `jobs` block in the next step before it can run.

    ```yaml
    name: Run Tests

    on:
      push:
        branches: [main]
      pull_request:
        branches: [main]

    permissions:
      contents: read

    concurrency:
      group: ci-${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}
      cancel-in-progress: ${{ github.event_name == 'pull_request' }}

    env:
      PYTHONDONTWRITEBYTECODE: '1'
    ```

3. Append this initial `jobs` block below the header. Later steps add the browser and build jobs; the [complete stage 3 snapshot][test-solution] includes all three.

    ```yaml
    jobs:
      test-api:
        runs-on: ubuntu-latest
        timeout-minutes: 10
        steps:
          - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              persist-credentials: false

          - name: Set up Python
            uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
            with:
              python-version: '3.13'

          - name: Install Python dependencies
            run: python -m pip install -r app/server/requirements.txt

          - name: Run tests
            working-directory: app/server
            env:
              DATABASE_PATH: ':memory:'
            run: python -m unittest test_app -v
    ```

4. Save the file.

Notice how this workflow differs from the hello world:
- It triggers on `push` and `pull_request` events instead of `workflow_dispatch` — so it runs automatically when a PR or merge is made to the specified branch(es).
- It declares explicit **`permissions`** — we'll explain this next.
- It uses a pinned `actions/checkout` to clone your repository, without leaving the token in Git configuration.
- It uses a pinned `actions/setup-python` to install Python 3.13.
- Next, it installs the necessary libraries using `pip`, just like you normally would.
- Finally, it's time to run the tests - again, just like before!

The API imports initialize a database before the tests mock queries, so `DATABASE_PATH: ':memory:'` protects the checked-in shelter database. `PYTHONDONTWRITEBYTECODE: '1'` avoids generated Python bytecode. Keep both settings in later refactors.

Concurrency groups PR runs by PR number, cancelling obsolete validation after another push to that PR. Non-PR runs use their unique run ID, so one `main` push doesn't cancel another. Each runner job has a finite timeout.

## Understanding `GITHUB_TOKEN` and permissions

Every workflow run automatically receives a token called **`GITHUB_TOKEN`**. This is a short-lived credential that actions use behind the scenes to interact with your repository — for example, `actions/checkout` uses it to clone your code. The token is created when the workflow starts and revoked when the run ends.

The **`permissions`** block controls what this token can do. For our CI workflow, we only need `contents: read` — enough to clone the repository. This follows the [principle of least privilege][principle-least-privilege]: grant only the permissions your workflow actually needs, nothing more.

> [!IMPORTANT]
> Always set explicit `permissions` in your workflows. Without it, the token inherits the repository-level defaults (**Settings** > **Actions** > **General** > **Workflow permissions**), which may be more permissive than your workflow requires. Being explicit ensures your workflow only has the access it needs — even if someone changes the repository defaults later.

## Push and explore

A bit later you'll use a more standard branching approach for changes. But for our purposes right now, let's push straight to `main`. What you'll notice is the workflow will automatically run, since the workflow will now exist on `main`!

1. Open the terminal in your codespace by pressing <kbd>Ctl</kbd>+<kbd>`</kbd>, then stage, commit, and push:

    ```bash
    git add .github/workflows/run-tests.yml
    git commit -m "Add CI workflow with unit tests"
    git push
    ```

2. Navigate to the **Actions** tab — the **Run Tests** workflow should already be running (triggered by the push).
3. Select the **test-api** job and explore the logs. Notice the flow of checkout, Python setup, and dependency installation.

## Add e2e tests in parallel

The unit tests cover the API, but the shelter also has Playwright e2e tests that verify the full application works end-to-end in a real browser. Let's add a second job that runs alongside the unit tests.

1. Return to your codespace and open `.github/workflows/run-tests.yml`. Add the following job to the bottom of the file:

    ```yaml
      test-e2e:
        runs-on: ubuntu-latest
        timeout-minutes: 15
        steps:
          - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              persist-credentials: false

          - name: Set up Python
            uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
            with:
              python-version: '3.13'

          - name: Install Python dependencies
            run: python -m pip install -r app/server/requirements.txt

          - name: Set up Node.js
            uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
            with:
              node-version: '22'

          - name: Install Node dependencies
            working-directory: app/client
            run: npm ci

          - name: Install Playwright browsers
            working-directory: app/client
            run: npx playwright install --with-deps chromium

          - name: Run e2e tests
            working-directory: app/client
            run: npx playwright test --project=chromium
    ```

2. Save the file.

> [!NOTE]
> Because we haven't added a `needs` key, `test-api` and `test-e2e` will run **in parallel**. Each job gets its own runner, so they don't interfere with each other and the total CI time is closer to the duration of the slower job rather than the sum of both. The `test-e2e` job needs both Python and Node.js because the Playwright tests launch the full stack — the Flask API and the Astro frontend — before running browser tests against them.

1. In the terminal, stage, commit, and push:

    ```bash
    git add .github/workflows/run-tests.yml
    git commit -m "Add e2e tests running in parallel"
    git push
    ```

2. Navigate to the **Actions** tab and select the new workflow run. You should see both **test-api** and **test-e2e** running side by side.

Node `'22'` selects a current 22.x release, which must be at least 22.12 for the checked-in frontend dependencies. Playwright's existing configuration launches Flask and Astro and seeds an isolated e2e database; don't add another server or point it at the shelter's tracked database.

## Add a frontend build check

Browser tests use the development server. A production build can fail independently, so the shelter needs a third check.

1. Add this job under `jobs`, alongside the test jobs:

    ```yaml
      build-client:
        runs-on: ubuntu-latest
        timeout-minutes: 10
        steps:
          - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
            with:
              persist-credentials: false
          - name: Set up Node.js
            uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
            with:
              node-version: '22'
          - name: Install Node dependencies
            working-directory: app/client
            run: npm ci
          - name: Build frontend
            working-directory: app/client
            run: npm run build
    ```

2. Commit and push `run-tests.yml`. Confirm all three jobs succeed.
3. Compare your file with the [complete stage 3 solution][test-solution], installed as `.github/workflows/run-tests.yml`.

Keep the workflow name **Run Tests**: the Azure lesson listens for this exact name. Don't hide test failures with `continue-on-error`. If a check fails, inspect its first failing command; the [troubleshooting guide][troubleshooting] covers common errors. The [artifact lesson][artifacts] adds retained Playwright reports and traces.

## Summary and next steps

You've built a CI pipeline with three parallel checks: API unit tests, browser tests, and a frontend production build. Each runs with read-only permissions and a bounded runtime.

Now, let's work to [improve the performance of our CI job][walkthrough-next] by reusing steps and caching dependencies.

## Resources

- [GitHub Actions documentation][github-actions-docs]
- [Workflow syntax for GitHub Actions][workflow-syntax]
- [Events that trigger workflows][workflow-triggers]
- [Using jobs in a workflow][jobs-docs]
- [Automatic token authentication][automatic-token-auth]
- [Assigning permissions to jobs][permissions-docs]

| [← Securing the Development Pipeline][walkthrough-previous] | [Next: Caching →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[action-versioning]: https://docs.github.com/actions/how-tos/write-workflows/choose-what-workflows-do/find-and-customize-actions#using-release-management-for-your-custom-actions
[artifacts]: 10-artifacts-and-reports.md
[test-solution]: solutions/03-running-tests/run-tests.yml
[troubleshooting]: troubleshooting.md
[actions-marketplace]: https://github.com/marketplace?type=actions
[automatic-token-auth]: https://docs.github.com/actions/security-for-github-actions/security-guides/automatic-token-authentication
[github-actions-docs]: https://docs.github.com/actions
[introduction]: 1-introduction.md
[jobs-docs]: https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/using-jobs-in-a-workflow
[marketplace-badges]: https://docs.github.com/actions/how-tos/create-and-publish-actions/publish-in-github-marketplace#about-badges-in-github-marketplace
[permissions-docs]: https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/assigning-permissions-to-jobs
[playwright]: https://playwright.dev/
[principle-least-privilege]: https://docs.github.com/actions/security-for-github-actions/security-guides/automatic-token-authentication#permissions-for-the-github_token
[workflow-syntax]: https://docs.github.com/actions/writing-workflows/workflow-syntax-for-github-actions
[workflow-triggers]: https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows
[walkthrough-previous]: 2-code-scanning.md
[walkthrough-next]: 4-caching.md
