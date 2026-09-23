# Rulesets, Required Workflows & Core Checkpoint

| [← Reusable Workflows][walkthrough-previous] | [Next: Artifacts & Reports →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

Building CI/CD checks doesn't make them required. Repository rulesets control whether code can merge without passing checks and getting reviewed. Required workflows let eligible organizations mandate a specific workflow across repositories. In this final core exercise, you'll configure a ruleset on `main`, explore the organizational option, and prepare for the advanced labs.

## Scenario

The shelter's CI/CD pipeline is comprehensive, but nothing currently prevents someone from merging code without passing CI — meaning untested code could reach `main` and trigger a deployment. The organization also wants to ensure all repositories run security scanning. Let's lock things down with rulesets and explore how required workflows enforce standards at scale.

## Background

### Repository rulesets

[Rulesets][about-rulesets] are GitHub's recommended approach for enforcing rules on branches and tags. They offer flexibility and visibility that legacy branch protection rules don't:

- **Layering** — Multiple rulesets can apply to the same branch; the most restrictive rule wins.
- **Status management** — Toggle between **Active** and **Disabled** without losing configuration.
- **Visibility** — Anyone with read access can see active rulesets (not just admins).
- **Bypass permissions** — Granular bypass for specific roles, teams, or GitHub Apps.
- **Scope**: Repository-level or organization-wide, depending on the plan and rule.
- **Required workflows**: An organization rule can require a selected workflow. This differs from a repository's required status check.

Rulesets are available on all GitHub plans for public repositories, and on GitHub Pro, Team, and Enterprise plans for private repositories.

### Required workflows

One of the most powerful ruleset features is the ability to **require specific workflows to pass before merging**. This is particularly useful at the organization level:

- An organization creates a workflow with supported required-workflow triggers in a central repository.
- An organization-wide ruleset requires that workflow for all (or a subset of) repositories.
- Every PR across those repositories now runs the required workflow automatically — individual repository owners can't skip it.

Common use cases include security scanning, license compliance, and code quality checks.

## Add a summary job to the CI workflow

Our CI has a Python API matrix, Playwright browser tests, and a frontend build. A stable aggregate check lets branch rules keep the same name as implementation details change. Add `tests-passed`, which explicitly requires all three jobs to succeed.

1. Open `.github/workflows/run-tests.yml` and add this job at the end of `jobs`, after `build-client`:

    ```yaml
      tests-passed:
        if: always()
        needs: [test-api, test-e2e, build-client]
        runs-on: ubuntu-latest
        timeout-minutes: 5
        steps:
          - name: Check results
            env:
              API_RESULT: ${{ needs.test-api.result }}
              E2E_RESULT: ${{ needs.test-e2e.result }}
              BUILD_RESULT: ${{ needs.build-client.result }}
            run: |
              if [[ "$API_RESULT" != "success" || "$E2E_RESULT" != "success" || "$BUILD_RESULT" != "success" ]]; then
                echo "::error::Every required job must succeed (failed, cancelled, and skipped jobs are rejected)."
                exit 1
              fi
              printf '## Required checks\n\nAPI, browser tests, and frontend build passed.\n' >> "$GITHUB_STEP_SUMMARY"
    ```

2. Commit and push the change:

    ```bash
    git add .github/workflows/run-tests.yml
    git commit -m "Add tests-passed summary job"
    git push
    ```

`if: always()` schedules the gate even after an upstream failure or skip. The explicit comparisons reject **failure**, **cancelled**, and **skipped**, not only failures. A cancelled whole workflow may prevent the gate from finishing, but must never count as a successful required check. Keep matrix `fail-fast: false` and don't mark required jobs `continue-on-error`.

The [complete gate solution][gate-solution] replaces `.github/workflows/run-tests.yml` and retains lesson 7's composite action. For a fresh CI installation, also copy [the companion action][action-solution] to `.github/actions/setup-python-env/action.yml`. Keep lesson 8's deployment files only if you opted into Azure.

## Create a ruleset for `main`

Let's create a ruleset that requires our tests to pass, and pull requests to be reviewed, before merging to `main`.

1. Navigate to your repository on GitHub.
2. Select **Settings**, then in the left sidebar under **Code and automation**, expand **Rules** and select **Rulesets**.
3. Select **New ruleset** > **New branch ruleset**.
4. Under **Ruleset name**, enter `main-gate`.
5. Set the **Enforcement status** to **Active**.
6. Under **Target branches**, select **Add target** > **Include default branch**. This targets `main`.
7. Under **Branch rules**, enable the following rules:

    | Rule | Configuration |
    |------|--------------|
    | **Require a pull request before merging** | Set **Required approvals** to `1` |
    | **Require status checks to pass** | Check **Require branches to be up to date before merging**, then add `tests-passed` as a required check |
    | **Block force pushes** | *(enabled by default)* |

8. Select **Create** to save the ruleset.

> [!TIP]
> If your status checks don't appear when searching, make sure the CI workflow has run at least once on the repository. GitHub only shows status checks that have been reported previously.

> [!NOTE]
> **Disabled** means no enforcement, not a preview of blocking behavior. Use **Evaluate** only if your plan exposes it; otherwise test an **Active** rule in this disposable training repository. Keep bypass access narrow and understand who can still merge.

You need another collaborator to satisfy an approving-review rule; a PR author can't approve their own PR. Solo learners can observe the blocked PR and close it, or arrange a review with the workshop leader. Don't remove protection and claim that approval was verified.

## Test the ruleset

Let's verify the ruleset is working.

1. Return to your codespace and open the terminal (<kbd>Ctl</kbd>+<kbd>`</kbd> to toggle). Create a new branch and make a small change:

    ```bash
    git checkout -b test-ruleset
    echo "# test change" >> app/server/app.py
    git add app/server/app.py
    git commit -m "Test ruleset enforcement"
    git push -u origin test-ruleset
    ```

2. Navigate to your repository on GitHub and create a pull request from `test-ruleset` to `main`.
3. Observe that the **Merge pull request** button is disabled — the required status checks must pass and the PR needs an approving review.
4. Watch the CI workflow run. Even after all checks pass, the merge button remains disabled until the review requirement is satisfied.
5. You can close the pull request — the important thing is that the ruleset is enforced!

> [!IMPORTANT]
> Rulesets enforce the configured checks and reviews for actors without bypass access. The automatic Azure path additionally checks a successful same-repository `main` push and deploys its exact SHA. Manual rollback is a separate trusted-operator exception, not proof that CI ran for that manual deployment.

## Verify the gate fails closed

1. In the practice PR, add a temporary `run: exit 1` step to `build-client`. Confirm both the build and `tests-passed` fail.
2. Replace that failure with a job-level `if: false` on `build-client`. Confirm the skipped build also makes `tests-passed` fail.
3. Remove the temporary changes. Confirm all three dependencies and the gate pass.
4. Push two quick updates to the PR and observe obsolete validation being cancelled. The newest run must independently pass. A cancelled or pending required check isn't a successful check.

Don't add path filters that skip the entire required workflow for some PRs: the expected check can remain pending indefinitely. Keep the job ID/name `tests-passed` unique and stable. If you enable merge queues later, add the required `merge_group` trigger and validate that path before requiring it.

## Organizational required workflows

This is an owner-led extension, not required to complete the core. Organization-wide rulesets and **Require workflows to pass before merging** have distinct feature availability. Organization rulesets are available on Team and Enterprise plans; requiring a selected workflow is an Enterprise Cloud capability. Verify the [current organization rules documentation][organization-rules] before promising it for a training organization.

1. Ask the organization owner to choose a central workflow repository and a small set of training targets. Confirm Actions is enabled and the workflow is accessible to every target repository under its visibility and sharing policy.
2. Configure a workflow using the supported required-workflow events, such as `pull_request`; include `merge_group` if the targets use merge queues. A `workflow_call`-only reusable workflow isn't by itself a ruleset-triggered entry point. An event-triggered wrapper can call a reusable workflow.
3. Add the selected workflow to an organization branch ruleset targeting the default branch and test it on a training PR before broad enforcement. Don't target every working branch: required workflows run through PRs and merge queues, so the rule blocks direct pushes. Event filters are ignored for ruleset workflows; use ruleset targeting rather than a YAML branch filter. Review token permissions and the fork-PR trust boundary just as you did for local CI.
4. If your plan doesn't expose the rule, keep the repository's `tests-passed` requirement and review the organizational configuration with the instructor. A repository check is useful, but it isn't equivalent to centrally enforced workflow identity.

## Advanced features to explore

Here are some additional GitHub Actions features you can explore on your own:

- **Service containers**: Spin up databases, caches, or other services alongside your test jobs. Define them under `services` in a job, and GitHub Actions handles the lifecycle for you.
- **Job summaries**: Write Markdown to the `$GITHUB_STEP_SUMMARY` environment file to create rich, formatted output that appears on the workflow run summary page.
- **Self-hosted runners**: Run workflows on your own infrastructure for specialized hardware needs, compliance requirements, or to stay within your network. Useful when you need GPUs, specific OS versions, or access to internal resources.
- **Larger runners**: GitHub-hosted runners with additional capacity, subject to plan, billing, and owner configuration. See the [larger runners documentation][larger-runners] and the advanced runner lab before changing labels.
- **`repository_dispatch`**: Trigger workflows from external events via the GitHub API. This is useful for integrating GitHub Actions with external systems like monitoring tools, chatbots, or other CI/CD platforms.

## Core complete: summary and next steps

Congratulations! You've built a complete CI/CD pipeline for the pet shelter application. Let's review what you've accomplished:

- **Continuous integration**: Tests run on every push and pull request across multiple Python versions, catching bugs before they reach `main`.
- **Continuous deployment**: Automated deployment to Azure via `azd`, triggered after CI passes on `main`.
- **Custom actions**: Shared validated Python setup, dependency caching, and installation without changing test database behavior.
- **Reusable workflows**: Extracted the deployment pattern into a callable workflow template, shared by both the automated CD pipeline and a manual deploy workflow for rollbacks.
- **Manual deployment**: Added a default-branch-only trusted-operator path with a separate reviewed rollback SHA.
- **Rulesets**: Enforced quality gates so code can't be merged without passing CI checks and peer review — the production safeguard that ensures only validated code gets deployed.

If you skipped Azure, your completed result is the tested CI pipeline and repository gate; cloud deployment remains optional. Keep that boundary explicit when describing what you've verified.

Next, continue with [Artifacts & Reports][walkthrough-next] to retain build outputs and diagnose failed browser runs. The advanced path adds runner administration, protected environments, safe AI exercises, and an integrated capstone without replacing the core lessons.

### Continue learning

If you want to keep exploring, here are some suggested next steps:

- Review the CodeQL and Dependabot results from lesson 2.
- Explore [GitHub Environments][environments-docs] with deployment protection rules for staged deployments (e.g., staging → production with manual approval).
- Explore the [GitHub Actions Marketplace][actions-marketplace] for community-built actions.
- Take the [GitHub Skills: Deploy to Azure][skills-deploy-azure] course for a deeper dive into Azure deployment.

## Resources

- [About rulesets][about-rulesets]
- [Creating rulesets for a repository][creating-rulesets]
- [Available rules for rulesets][available-rules]
- [The `workflow_dispatch` event][workflow-dispatch]
- [GitHub Skills: Deploy to Azure][skills-deploy-azure]
- [GitHub Actions Marketplace][actions-marketplace]

| [← Reusable Workflows][walkthrough-previous] | [Next: Artifacts & Reports →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[about-rulesets]: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
[action-solution]: solutions/09-required-workflows/setup-python-env/action.yml
[gate-solution]: solutions/09-required-workflows/run-tests.yml
[organization-rules]: https://docs.github.com/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-workflows-to-pass-before-merging
[actions-marketplace]: https://github.com/marketplace?type=actions
[available-rules]: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
[creating-rulesets]: https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
[environments-docs]: https://docs.github.com/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment
[github-security]: https://github.com/features/security
[larger-runners]: https://docs.github.com/actions/using-github-hosted-runners/using-larger-runners
[skills-deploy-azure]: https://github.com/skills/deploy-to-azure
[workflow-dispatch]: https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_dispatch
[walkthrough-previous]: 8-reusable-workflows.md
[walkthrough-next]: 10-artifacts-and-reports.md
