# GitHub Actions: From CI to CD

| [← Pets workshop selection][walkthrough-previous] | [Next: Workshop Setup →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[GitHub Actions][github-actions] lets you build, test, and deploy code from your
repository. The core workshop builds a CI/CD pipeline for the shelter application,
from automated tests to Azure deployment. An optional advanced continuation adds
artifacts, runner choices, human approval, and bounded AI-assisted automation.

## Scenario

You're a developer, volunteering for a pet adoption shelter. They have a [Flask][flask] API and an [Astro][astro] frontend. They're ready to productionize their app, and deploy it to the cloud! But they also know there's some processes that should be followed to ensure everything flows smoothly. The goal is to work to automate all of those - through the use of GitHub Actions!

## Prerequisites

To complete this workshop, you will need the following:

- A [GitHub account][github-signup]
- Python 3.13 and Node.js 22 (22.12.0 or newer), or a development environment with
  those runtimes
- An [Azure subscription][azure-free] only for the Azure deployment exercises
- Familiarity with Git basics (commit, push, pull)

Repository-owner access is needed to configure rulesets and environments. Advanced
approval exercises need supported environment protection rules and another eligible
reviewer. Self-hosted hardware and an eligible Copilot plan are optional, not
prerequisites for the credential-free advanced labs. See [setup][setup] for the
owner/learner boundaries.

> [!NOTE]
> If you have access to [GitHub Copilot][github-copilot], it can help you write workflow YAML files. You'll see tips throughout the exercises on how to use it effectively.

## Core exercises

0. [Workshop Setup][setup] — Create your repository from the template
1. [Introduction & Your First Workflow][introduction] — Create your first workflow and explore the Actions UI
2. [Securing the Development Pipeline][code-scanning] — Enable code scanning, Dependabot, and secret scanning
3. [Running Tests][ci] — Automate unit and e2e testing with parallel jobs
4. [Caching][marketplace] — Speed up workflows by caching dependencies
5. [Matrix strategies & parallel testing][matrix] — Test across multiple configurations simultaneously
6. [Deploying to Azure with azd][deployment] — Set up continuous deployment to Azure
7. [Creating custom actions][custom-actions] — Build your own reusable action
8. [Reusable workflows][reusable-workflows] — Share workflow logic across repositories
9. [Rulesets and required workflows][protection]: Enforce standards and finish the core track

## Optional advanced exercises

Continue in order to combine these ideas, or use the prerequisites in each lesson
to choose an individual lab. Azure remains the deployment target; the artifact and
approval exercises do not require a cloud account.

| Lesson | What you'll do |
| --- | --- |
| [10. Artifacts and test reports][artifacts] | Keep Playwright diagnostics, transfer a build between jobs, and verify checksums. |
| [11. Runners and hardware][runners] | Run a small cross-OS test matrix and explore runner access, cost, and optional self-hosted setup. |
| [12. Protected environments][environments] | Observe reviewer approval with no credentials, then optionally protect Azure deployment. |
| [13. GitHub Copilot CLI][copilot-cli] | Start with a dry run and optionally approve a restricted, read-only CLI invocation. |
| [14. Agentic workflows][agentic] | Simulate planning, bounded execution, validation, and human review without a model or autonomous writes. |
| [15. Capstone][capstone] | Combine CI gates, artifact verification, post-merge checks, and optional approved Azure deployment. |

## Examples and troubleshooting

Follow the exercises to build your own workflows. [Complete solutions][solutions]
are stored under `content/github-actions/solutions/`, **not**
`.github/workflows`. They do nothing until you copy the selected files to the
documented destinations. Creating a repository from this template does not activate
these examples.

Use the [troubleshooting reference][troubleshooting] to diagnose failures, and the
[local validation instructions][validation] when maintaining workshop content.
Do not copy all solution stages at once: later stages replace or extend earlier
files deliberately.

The AI workflow defaults do not call a model. The agentic lesson is a simulation,
not a complete live-agent implementation. Checksummed builds are not attestations,
and `azd up` may rebuild rather than promote the uploaded build artifact.

## Resources

- [GitHub Actions documentation][github-actions-docs]
- [GitHub Actions Marketplace][actions-marketplace]
- [Workflow syntax reference][workflow-syntax]
- [Azure Developer CLI (azd) documentation][azd-docs]

| [← Pets workshop selection][walkthrough-previous] | [Next: Workshop Setup →][walkthrough-next] |
|:-----------------------------------|------------------------------------------:|

[actions-marketplace]: https://github.com/marketplace?type=actions
[astro]: https://astro.build/
[azure-free]: https://azure.microsoft.com/free/
[azd-docs]: https://learn.microsoft.com/azure/developer/azure-developer-cli/overview
[ci]: ./3-running-tests.md
[code-scanning]: ./2-code-scanning.md
[custom-actions]: ./7-custom-actions.md
[deployment]: ./6-deploy-azure.md
[flask]: https://flask.palletsprojects.com/
[github-actions]: https://github.com/features/actions
[github-actions-docs]: https://docs.github.com/actions
[github-copilot]: https://github.com/features/copilot
[github-signup]: https://github.com/join
[introduction]: ./1-introduction.md
[marketplace]: ./4-caching.md
[matrix]: ./5-matrix-strategies.md
[protection]: ./9-required-workflows.md
[repo-root]: /
[reusable-workflows]: ./8-reusable-workflows.md
[setup]: ./0-setup.md
[artifacts]: ./10-artifacts-and-reports.md
[runners]: ./11-runners-and-hardware.md
[environments]: ./12-protected-environments.md
[copilot-cli]: ./13-copilot-cli.md
[agentic]: ./14-agentic-workflows.md
[capstone]: ./15-capstone.md
[solutions]: ./solutions/README.md
[validation]: ./solutions/README.md#maintaining-the-examples
[troubleshooting]: ./troubleshooting.md
[walkthrough-next]: ./0-setup.md
[walkthrough-previous]: ../README.md
[workflow-syntax]: https://docs.github.com/actions/writing-workflows/workflow-syntax-for-github-actions
