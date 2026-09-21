# Caching

| [← Running Tests][walkthrough-previous] | [Next: Matrix Strategies & Parallel Testing →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

The [GitHub Actions Marketplace][actions-marketplace] is a collection of pre-built actions created by GitHub and the community. Actions can set up tools, run tests, deploy code, send notifications, and much more. Rather than writing everything from scratch, you can leverage the work of thousands of developers.

In this exercise you'll also learn about **caching** — a technique to speed up your workflows by reusing previously downloaded dependencies instead of fetching them from the internet on every run.

## Scenario

The CI workflow from the previous exercise works, but its three jobs download dependencies on each run. The shelter wants faster feedback without skipping installation or tests.

## Background

[Caching][caching-docs] stores downloaded dependencies between workflow runs so they don't need to be fetched from the internet every time. Each cache is identified by a key — typically derived from the package manager and lock file. When a workflow runs, it checks for an existing cache matching that key. On a hit, the cached files are restored and the install step completes in seconds. On a miss, the dependencies are downloaded normally and then saved for next time.

Many popular setup actions, including `actions/setup-python` and `actions/setup-node`, have caching built in. Cache storage, retention, and eviction follow your repository's current limits. A cache is disposable: the workflow must still work on a cache miss.

## Add caching to the unit test job

Many popular setup actions have caching built right in. Let's start with the `test-api` job, which uses Python. Libraries are installed for Python using `pip`, which will become the key name. This instructs the workflow to cache any libraries installed using `pip`.

1. In your codespace, open `.github/workflows/run-tests.yml`.
2. Update the **Set up Python** step in the `test-api` job to enable pip caching:

    ```yaml
          - name: Set up Python
            uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
            with:
              python-version: '3.13'
              cache: pip
              cache-dependency-path: app/server/requirements.txt
    ```

> [!NOTE]
> The `cache: 'pip'` option tells `setup-python` to cache downloaded pip packages. On the first run it saves the cache; on subsequent runs it restores it, skipping most download time.

3. Save the file.

## Add caching to the e2e test job

The e2e job can reuse Python and npm download caches. The cache key uses the server requirements file or client lockfile, so changing those files selects a different cache. Installation still runs on every job, including a cache hit.

1. Update the **Set up Python** step in the `test-e2e` job the same way:

    ```yaml
          - name: Set up Python
            uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
            with:
              python-version: '3.13'
              cache: pip
              cache-dependency-path: app/server/requirements.txt
    ```

2. Update the **Set up Node.js** step in the `test-e2e` job to enable npm caching:

    ```yaml
          - name: Set up Node.js
            uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
            with:
              node-version: '22'
              cache: npm
              cache-dependency-path: app/client/package-lock.json
    ```

3. Apply the same Node.js setup change to the `build-client` job.
4. Save the file. Compare it with the [complete caching solution][cache-solution], which replaces `.github/workflows/run-tests.yml`.

Keep `python -m pip install -r app/server/requirements.txt` and `npm ci` in their jobs. `setup-node` caches npm's package downloads, not `node_modules`. The server requirements currently aren't version-locked, so caching doesn't make Python dependency resolution reproducible.

A dependency cache speeds up another installation. An [artifact][artifacts] retains a selected result, such as a build or test report, for inspection or transfer between jobs. Never cache credentials or assume a cache is a trusted deployment artifact.

> [!NOTE]
> You might wonder about caching Playwright browsers too. Playwright's [official CI guidance][playwright-ci] recommends running `npx playwright install --with-deps` on every run rather than caching browsers, since browser binaries are tightly coupled to the Playwright version and caching them can lead to subtle version mismatches.

## Compare run times

Now let's push the changes and see the impact of caching.

1. In the terminal (<kbd>Ctl</kbd>+<kbd>`</kbd> to toggle), stage, commit, and push your changes:

    ```bash
    git add .github/workflows/run-tests.yml
    git commit -m "Add caching to CI workflow"
    git push
    ```

2. Navigate to the **Actions** tab on GitHub and observe the workflow run.
3. Once it completes, check the logs for the setup steps. You should see output indicating a **cache miss** — this is expected on the first run since there's nothing cached yet.
4. To see caching in action, trigger a second run. You can push a small change (such as adding a comment to `run-tests.yml`) or use the GitHub UI:
   - Open the completed run and choose **Re-run all jobs**

5. On the second run, check the setup step logs again. You should see a **cache hit**, and the overall run time should be noticeably shorter.

> [!TIP]
> You can view cache usage for your repository by navigating to **Actions** > **Caches** in the left sidebar. This shows all active caches, their sizes, and when they were last used.

## Summary and next steps

The Actions Marketplace provides thousands of pre-built actions so you don't have to reinvent the wheel. Many setup actions like `setup-python` and `setup-node` have caching built in, making it easy to dramatically reduce workflow run times by reusing previously downloaded dependencies.

Next, we'll explore [matrix strategies][walkthrough-next] to test across multiple configurations simultaneously.

## Resources

- [GitHub Actions Marketplace][actions-marketplace]
- [Caching dependencies to speed up workflows][caching-docs]
- [Playwright CI documentation][playwright-ci]
- [actions/setup-python][setup-python-action]
- [actions/setup-node][setup-node]

| [← Running Tests][walkthrough-previous] | [Next: Matrix Strategies & Parallel Testing →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[actions-marketplace]: https://github.com/marketplace?type=actions
[artifacts]: 10-artifacts-and-reports.md
[cache-solution]: solutions/04-caching/run-tests.yml
[caching-docs]: https://docs.github.com/actions/writing-workflows/choosing-what-your-workflow-does/caching-dependencies-to-speed-up-workflows
[marketplace]: https://github.com/marketplace
[playwright-ci]: https://playwright.dev/docs/ci
[setup-node]: https://github.com/actions/setup-node
[setup-python-action]: https://github.com/actions/setup-python
[walkthrough-previous]: 3-running-tests.md
[walkthrough-next]: 5-matrix-strategies.md
