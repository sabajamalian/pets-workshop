# Runners and Hardware

| [Previous: Artifacts and test reports][walkthrough-previous] | [Next: Protected environments][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

## Scenario

The shelter's volunteers develop on different operating systems. Before buying
larger machines or maintaining a private runner, the team wants to understand which
platforms its API supports and where workflow time is spent.

## Background

GitHub-hosted runners provide fresh managed execution environments. A self-hosted
runner is a machine you maintain, patch, isolate, and monitor. A self-hosted job can
reach that machine's files and network; a runner label is routing, not isolation.

| Choice | What to consider |
| --- | --- |
| Standard hosted runners | Convenient clean environments, with OS-dependent images, capacity, and billing. |
| Larger hosted runners | More CPU, memory, or network options; availability and billing depend on the plan and runner type. |
| Self-hosted runners | Private-network or specialized hardware access, with responsibility for isolation, updates, cleanup, and infrastructure cost. |
| ARM or GPU hardware | Architecture/library compatibility and an actual workload that benefits from it, not simply a faster-sounding label. |

Runner **groups** control access to a pool. **Labels** select eligible machines
within that access boundary. Every requested self-hosted label must match.

## Test the API across operating systems

1. Copy the [complete runner workflow][solution]:

    ```bash
    mkdir -p .github/workflows
    cp content/github-actions/solutions/11-runners/runner-matrix.yml .github/workflows/runner-matrix.yml
    ```

2. Inspect its matrix:

    ```yaml
    strategy:
      fail-fast: false
      max-parallel: 2
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    ```

3. Commit and push the workflow to the default branch. Run **Runner Matrix** from
   the Actions tab.
4. Compare each job's OS, architecture, queue time, and execution time. The lab runs
   only the API unit tests, not three full browser suites.
5. Confirm every job uses Python 3.13 and an in-memory test database.

The observation step selects Bash explicitly; otherwise `run` steps can use
different default shells on different platforms. The Python commands themselves
are portable. `fail-fast: false` keeps other platforms running after a failure.

> [!NOTE]
> A label ending in `-latest` can move to a newer image. Use a supported explicit
> image version when your workload needs it. Check current runner availability and
> pricing rather than assuming all labels have the same architecture or cost.

## Diagnose a queued job

1. On a practice branch, change `ubuntu-latest` to `ubuntu-never`.
2. Dispatch the workflow on that branch and inspect the waiting job.
3. Cancel the run. A job timeout is not a substitute for diagnosing a job that
   cannot obtain a runner.
4. Restore the label and rerun.

Measure queue time separately from test duration. Check concurrency and pool access
before assuming more CPU will solve a scheduling problem.

## Optional: register a disposable self-hosted runner

This section is for a repository or organization owner with an isolated disposable
machine. The hosted lab above does not require it.

1. Choose a private practice repository with trusted contributors. Do not register
   a persistent runner for untrusted public pull requests.
2. Open **Settings > Actions > Runners > New self-hosted runner**. For an
   organization, create or select a runner group restricted to the practice
   repository and trusted workflows where supported.
3. Choose the machine's OS and architecture. Follow GitHub's current generated
   download, verification, registration, and start instructions on that machine.
   Never save the short-lived registration token in a repository, report, or log.
4. Add a custom label such as `pets-workshop`. Inspect the actual assigned labels;
   a trusted manual job might target `[self-hosted, linux, ARM64, pets-workshop]`
   only if those labels exist.
5. Run a harmless observation command from a reviewed workflow on a protected
   branch. `workflow_dispatch` alone is not a security boundary if untrusted
   contributors can change the workflow or select an untrusted ref.
6. After the exercise, remove the registration through GitHub, stop the runner,
   and dispose of the dedicated test machine and its files.

Do not open inbound public ports to make the runner work. Review its outbound
connectivity and status instead. Ephemeral runners and autoscaling need additional
lifecycle controls and are beyond this registration exercise.

## Summary and next steps

You've tested the API on three platforms and separated runner routing, access,
performance, and cost decisions. Next, we'll add a [human approval step][walkthrough-next]
without needing cloud credentials.

## Resources

- [GitHub-hosted runners][hosted]
- [Adding self-hosted runners][self-hosted]
- [Runner groups][groups]
- [Actions billing][billing]

| [Previous: Artifacts and test reports][walkthrough-previous] | [Next: Protected environments][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[walkthrough-previous]: 10-artifacts-and-reports.md
[walkthrough-next]: 12-protected-environments.md
[solution]: solutions/11-runners/runner-matrix.yml
[hosted]: https://docs.github.com/actions/using-github-hosted-runners/about-github-hosted-runners
[self-hosted]: https://docs.github.com/actions/how-tos/manage-runners/self-hosted-runners/add-runners
[groups]: https://docs.github.com/actions/how-tos/manage-runners/self-hosted-runners/manage-access
[billing]: https://docs.github.com/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions
